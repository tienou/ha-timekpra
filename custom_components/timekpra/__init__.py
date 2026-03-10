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


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Timekpra and deploy the custom Lovelace card."""
    hass.data.setdefault(DOMAIN, {})

    # Copy card JS to HA www/ folder (served at /local/)
    src = Path(__file__).parent / "www" / CARD_JS
    dst = Path(hass.config.path("www"))
    dst.mkdir(exist_ok=True)
    dst = dst / CARD_JS
    try:
        shutil.copy2(str(src), str(dst))
        _LOGGER.debug("Timekpra card copied to %s", dst)
    except Exception:
        _LOGGER.warning("Could not copy card JS to %s", dst)

    # Register the JS so it loads on every page
    add_extra_js_url(hass, LOCAL_CARD_URL)

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
        hass, ssh, entry.data[CONF_TARGET_USER], entry.entry_id
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
