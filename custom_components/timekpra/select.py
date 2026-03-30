"""Select entities for the Timekpra integration."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOCKOUT_TYPES, PROFILE_CUSTOM
from .coordinator import TimekpraCoordinator
from .entity import TimekpraEntity
from .ssh import TimekpraSSH

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Timekpra select entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: TimekpraCoordinator = data["coordinator"]
    ssh: TimekpraSSH = data["ssh"]
    target_user: str = data["target_user"]

    async_add_entities([
        TimekpraLockoutType(coordinator, ssh, target_user, entry),
        TimekpraProfileSelect(coordinator, target_user, entry),
    ])


class TimekpraLockoutType(TimekpraEntity, SelectEntity):
    """Select what happens when time runs out (lock / suspend / shutdown)."""

    _attr_icon = "mdi:lock"
    _attr_options = LOCKOUT_TYPES

    def __init__(self, coordinator, ssh, target_user, entry) -> None:
        super().__init__(coordinator, target_user)
        self._ssh = ssh
        self._attr_unique_id = f"{entry.entry_id}_lockout_type"
        self._attr_name = "Action fin de temps"

    @property
    def current_option(self) -> str | None:
        return self.coordinator.data.get("lockout_type", "lock")

    async def async_select_option(self, option: str) -> None:
        self.coordinator.data["lockout_type"] = option
        self.async_write_ha_state()
        await self.coordinator.async_apply("set_lockout_type", option)


class TimekpraProfileSelect(TimekpraEntity, SelectEntity):
    """Select which profile to apply (École, Vacances, etc.)."""

    _attr_icon = "mdi:account-switch"

    def __init__(self, coordinator, target_user, entry) -> None:
        super().__init__(coordinator, target_user)
        self._attr_unique_id = f"{entry.entry_id}_profile"
        self._attr_name = "Profil"

    @property
    def options(self) -> list[str]:
        return self.coordinator.profile_names

    @property
    def current_option(self) -> str | None:
        return self.coordinator.active_profile

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_apply_profile(option)
        self.async_write_ha_state()
