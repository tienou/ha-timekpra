"""Timekpra parental control integration for Home Assistant."""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import async_get_integration

from .const import (
    CONF_SSH_HOST,
    CONF_SSH_HOST_VPN,
    CONF_SSH_KEY,
    CONF_SSH_KEY_PASSPHRASE,
    CONF_SSH_PASSWORD,
    CONF_SSH_PORT,
    CONF_SSH_USER,
    CONF_SUDO_PASSWORD,
    CONF_TARGET_USER,
    DOMAIN,
)
from .coordinator import TimekpraCoordinator
from .ssh import TimekpraSSH

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.NUMBER, Platform.SWITCH, Platform.SELECT, Platform.SENSOR]

CARD_JS = "timekpra-card.js"
# Served straight from the integration folder (HA-recommended way), no /config/www needed.
CARD_URL = f"/{DOMAIN}/{CARD_JS}"


@dataclass
class TimekpraRuntimeData:
    """Per-entry runtime objects, stored on the config entry."""

    coordinator: TimekpraCoordinator
    ssh: TimekpraSSH
    target_user: str


type TimekpraConfigEntry = ConfigEntry[TimekpraRuntimeData]


async def _async_card_version(hass: HomeAssistant) -> str:
    """Return the integration version (used as the card cache-buster).

    Reads the loaded integration metadata — no blocking file I/O in the loop.
    """
    integration = await async_get_integration(hass, DOMAIN)
    return str(integration.version or "0")


async def _register_card_frontend(hass: HomeAssistant, version: str) -> None:
    """Serve the Lovelace card and auto-load it in the frontend.

    HA-recommended approach: serve the JS via a static path, then register it
    as an extra frontend module so the card is available WITHOUT the user
    adding a dashboard resource by hand (works in storage and YAML modes).
    """
    from homeassistant.components.http import StaticPathConfig

    src = Path(__file__).parent / "www" / CARD_JS

    # 1. Serve the JS straight from the integration folder.
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, str(src), False)]
        )
    except RuntimeError:
        # Path already registered (set up earlier this run) — fine.
        pass
    except Exception:
        _LOGGER.warning("Could not register static path for the Timekpra card")
        return

    # 2. Auto-load it on the frontend. The version query busts the browser
    #    cache automatically on every upgrade.
    try:
        from homeassistant.components import frontend

        frontend.add_extra_js_url(hass, f"{CARD_URL}?v={version}")
        _LOGGER.info("Timekpra card auto-loaded from %s", CARD_URL)
    except Exception:
        _LOGGER.warning(
            "Could not auto-load the Timekpra card. Add it manually as a "
            "dashboard resource: URL '%s', type 'JavaScript Module'.",
            CARD_URL,
        )


def _copy_card_to_www(src: Path, dst_dir: Path) -> None:
    """Blocking copy (runs in executor): mirror the card into /config/www."""
    dst_dir.mkdir(exist_ok=True)
    shutil.copy2(str(src), str(dst_dir / CARD_JS))


async def _deploy_card(hass: HomeAssistant) -> None:
    """Also mirror the card into /config/www (→ /local/).

    Backward compatibility for installs that already registered a
    ``/local/timekpra-card.js`` resource, and a manual-resource fallback.
    Auto-loading is handled by :func:`_register_card_frontend`.
    """
    src = Path(__file__).parent / "www" / CARD_JS
    dst_dir = Path(hass.config.path("www"))
    try:
        await hass.async_add_executor_job(_copy_card_to_www, src, dst_dir)
    except Exception:
        _LOGGER.warning("Could not copy card JS to %s", dst_dir)


@callback
def _register_services(hass: HomeAssistant) -> None:
    """Register the profile services once (integration-wide)."""
    if hass.services.has_service(DOMAIN, "save_profile"):
        return

    def _coordinator_for(call: ServiceCall) -> TimekpraCoordinator:
        loaded = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.state is ConfigEntryState.LOADED
            and getattr(e, "runtime_data", None)
        ]
        entry_id = call.data.get("entry_id")
        if entry_id:
            for e in loaded:
                if e.entry_id == entry_id:
                    return e.runtime_data.coordinator
            raise ServiceValidationError(f"No loaded Timekpra entry '{entry_id}'")
        if len(loaded) == 1:
            return loaded[0].runtime_data.coordinator
        raise ServiceValidationError(
            "Specify entry_id when multiple devices are configured"
        )

    async def _handle_save_profile(call: ServiceCall) -> None:
        await _coordinator_for(call).async_save_profile(call.data["name"])

    async def _handle_delete_profile(call: ServiceCall) -> None:
        await _coordinator_for(call).async_delete_profile(call.data["name"])

    profile_schema = vol.Schema(
        {
            vol.Required("name"): cv.string,
            vol.Optional("entry_id"): cv.string,
        }
    )
    hass.services.async_register(
        DOMAIN, "save_profile", _handle_save_profile, schema=profile_schema
    )
    hass.services.async_register(
        DOMAIN, "delete_profile", _handle_delete_profile, schema=profile_schema
    )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Timekpra: expose the Lovelace card and register services."""
    version = await _async_card_version(hass)
    await _register_card_frontend(hass, version)  # auto-load (recommended path)
    await _deploy_card(hass)  # /local fallback + backward compatibility
    _register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TimekpraConfigEntry) -> bool:
    """Set up Timekpra from a config entry."""
    ssh = TimekpraSSH(
        host=entry.data[CONF_SSH_HOST],
        port=entry.data[CONF_SSH_PORT],
        username=entry.data[CONF_SSH_USER],
        password=entry.data.get(CONF_SSH_PASSWORD, ""),
        host_vpn=entry.data.get(CONF_SSH_HOST_VPN, ""),
        ssh_key=entry.data.get(CONF_SSH_KEY, ""),
        ssh_key_passphrase=entry.data.get(CONF_SSH_KEY_PASSPHRASE, ""),
        sudo_password=entry.data.get(CONF_SUDO_PASSWORD, ""),
    )

    coordinator = TimekpraCoordinator(hass, entry, ssh)
    # _async_setup() (loads persisted state + wires host-key pinning) runs
    # automatically inside async_config_entry_first_refresh().
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = TimekpraRuntimeData(
        coordinator=coordinator,
        ssh=ssh,
        target_user=entry.data[CONF_TARGET_USER],
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload integration when options are changed
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    return True


async def _async_reload_entry(
    hass: HomeAssistant, entry: TimekpraConfigEntry
) -> None:
    """Reload the integration when config changes."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: TimekpraConfigEntry) -> bool:
    """Unload a config entry (runtime_data is cleared by HA automatically)."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
