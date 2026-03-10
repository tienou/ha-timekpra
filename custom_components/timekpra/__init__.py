"""Timekpra parental control integration for Home Assistant."""
from __future__ import annotations

import logging

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
