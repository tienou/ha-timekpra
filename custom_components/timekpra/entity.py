"""Base entity for the Timekpra integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TimekpraCoordinator


class TimekpraEntity(CoordinatorEntity[TimekpraCoordinator]):
    """Base class for all Timekpra entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TimekpraCoordinator, target_user: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._target_user = target_user

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info so all entities are grouped."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._target_user)},
            name=f"Timekpra {self._target_user.capitalize()}",
            manufacturer="Timekpr-nExT",
            model="Contr\u00f4le Parental",
        )
