"""Timekpra parental control integration for Home Assistant."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

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
LOCAL_CARD_URL = f"/local/{CARD_JS}"


async def _deploy_card(hass: HomeAssistant) -> None:
    """Copy the JS card to www/ and register it as a Lovelace resource."""
    # 1. Copy JS to www/
    src = Path(__file__).parent / "www" / CARD_JS
    dst_dir = Path(hass.config.path("www"))
    dst_dir.mkdir(exist_ok=True)
    dst = dst_dir / CARD_JS
    try:
        shutil.copy2(str(src), str(dst))
        _LOGGER.debug("Timekpra card copied to %s", dst)
    except Exception:
        _LOGGER.warning("Could not copy card JS to %s", dst)
        return

    # 2. Load JS on every page
    add_extra_js_url(hass, LOCAL_CARD_URL)

    # 3. Register as Lovelace resource (so it shows in card picker)
    try:
        resources = hass.data.get("lovelace", {}).get("resources")
        if resources is not None:
            existing = [
                r for r in resources.async_items()
                if LOCAL_CARD_URL in r.get("url", "")
            ]
            if not existing:
                await resources.async_create_item(
                    {"res_type": "module", "url": LOCAL_CARD_URL}
                )
                _LOGGER.info("Registered Timekpra card as Lovelace resource")
            else:
                _LOGGER.debug("Timekpra card resource already registered")
        else:
            _LOGGER.debug("Lovelace resources not available")
    except Exception:
        _LOGGER.debug("Could not auto-register Lovelace resource", exc_info=True)


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
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
