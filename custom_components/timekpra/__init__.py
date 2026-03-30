"""Timekpra parental control integration for Home Assistant."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_SSH_HOST,
    CONF_SSH_PASSWORD,
    CONF_SSH_PORT,
    CONF_SSH_USER,
    CONF_TARGET_USER,
    DOMAIN,
)
from .coordinator import TimekpraCoordinator
from .ssh import TimekpraSSH

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.NUMBER, Platform.SWITCH, Platform.SELECT, Platform.SENSOR]

CARD_JS = "timekpra-card.js"


def _get_version() -> str:
    """Read version from manifest.json for cache-busting."""
    import json

    manifest = Path(__file__).parent / "manifest.json"
    try:
        return json.loads(manifest.read_text()).get("version", "0")
    except Exception:
        return "0"


async def _deploy_card(hass: HomeAssistant) -> None:
    """Copy the JS card to www/ and register it as a Lovelace resource."""
    src = Path(__file__).parent / "www" / CARD_JS
    dst_dir = Path(hass.config.path("www"))
    dst_dir.mkdir(exist_ok=True)
    dst = dst_dir / CARD_JS

    # Always copy — ensures updates are deployed after HACS upgrade
    try:
        await hass.async_add_executor_job(shutil.copy2, str(src), str(dst))
        version = _get_version()
        _LOGGER.info("Timekpra card v%s deployed to %s", version, dst)
    except Exception:
        _LOGGER.warning("Could not copy card JS from %s to %s", src, dst)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Timekpra and deploy the custom Lovelace card."""
    hass.data.setdefault(DOMAIN, {})
    await _deploy_card(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Timekpra from a config entry."""
    ssh = TimekpraSSH(
        host=entry.data[CONF_SSH_HOST],
        port=entry.data[CONF_SSH_PORT],
        username=entry.data[CONF_SSH_USER],
        password=entry.data[CONF_SSH_PASSWORD],
    )

    coordinator = TimekpraCoordinator(
        hass, ssh, entry.data[CONF_TARGET_USER], entry.data[CONF_SSH_HOST]
    )
    await coordinator.async_load_pending()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "ssh": ssh,
        "target_user": entry.data[CONF_TARGET_USER],
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ── Profile services ───────────────────────────────────────────
    async def _get_coordinator(call: ServiceCall) -> TimekpraCoordinator:
        entry_id = call.data.get("entry_id")
        if entry_id:
            return hass.data[DOMAIN][entry_id]["coordinator"]
        # If only one entry, use it automatically
        entries = list(hass.data[DOMAIN].values())
        if len(entries) == 1:
            return entries[0]["coordinator"]
        raise ValueError("Specify entry_id when multiple devices are configured")

    async def _handle_save_profile(call: ServiceCall) -> None:
        coordinator = await _get_coordinator(call)
        await coordinator.async_save_profile(call.data["name"])

    async def _handle_delete_profile(call: ServiceCall) -> None:
        coordinator = await _get_coordinator(call)
        await coordinator.async_delete_profile(call.data["name"])

    profile_schema = vol.Schema({
        vol.Required("name"): cv.string,
        vol.Optional("entry_id"): cv.string,
    })

    if not hass.services.has_service(DOMAIN, "save_profile"):
        hass.services.async_register(
            DOMAIN, "save_profile", _handle_save_profile, schema=profile_schema
        )
        hass.services.async_register(
            DOMAIN, "delete_profile", _handle_delete_profile, schema=profile_schema
        )

    # Reload integration when options are changed
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when config changes."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
