"""Sensor entities for the Timekpra integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TimekpraCoordinator
from .entity import TimekpraEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Timekpra sensor entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: TimekpraCoordinator = data["coordinator"]
    target_user: str = data["target_user"]

    async_add_entities(
        [
            TimekpraTimeSpentTodaySensor(coordinator, target_user, entry),
            TimekpraTimeRemainingSensor(coordinator, target_user, entry),
            TimekpraTimeSpentWeekSensor(coordinator, target_user, entry),
            TimekpraOnlineSensor(coordinator, target_user, entry),
            TimekpraPendingSensor(coordinator, target_user, entry),
        ]
    )


class TimekpraTimeSpentTodaySensor(TimekpraEntity, SensorEntity):
    """Sensor showing time spent today (minutes)."""

    _attr_icon = "mdi:timer-sand"
    _attr_native_unit_of_measurement = "min"

    def __init__(self, coordinator, target_user, entry) -> None:
        super().__init__(coordinator, target_user)
        self._attr_unique_id = f"{entry.entry_id}_time_spent_today"
        self._attr_name = "Temps utilis\u00e9 aujourd'hui"

    @property
    def native_value(self) -> int | None:
        seconds = self.coordinator.data.get("time_spent_today")
        if seconds is not None:
            return seconds // 60
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        seconds = self.coordinator.data.get("time_spent_today")
        if seconds is not None:
            h, remainder = divmod(seconds, 3600)
            m = remainder // 60
            attrs["formatted"] = f"{h}h{m:02d}"
            attrs["seconds"] = seconds
        return attrs


class TimekpraTimeRemainingSensor(TimekpraEntity, SensorEntity):
    """Sensor showing time remaining today (minutes)."""

    _attr_icon = "mdi:timer-alert-outline"
    _attr_native_unit_of_measurement = "min"

    def __init__(self, coordinator, target_user, entry) -> None:
        super().__init__(coordinator, target_user)
        self._attr_unique_id = f"{entry.entry_id}_time_remaining"
        self._attr_name = "Temps restant aujourd'hui"

    @property
    def native_value(self) -> int | None:
        seconds = self.coordinator.data.get("time_remaining")
        if seconds is not None:
            return seconds // 60
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        seconds = self.coordinator.data.get("time_remaining")
        if seconds is not None:
            h, remainder = divmod(seconds, 3600)
            m = remainder // 60
            attrs["formatted"] = f"{h}h{m:02d}"
            attrs["seconds"] = seconds
        return attrs


class TimekpraTimeSpentWeekSensor(TimekpraEntity, SensorEntity):
    """Sensor showing time spent this week (minutes)."""

    _attr_icon = "mdi:calendar-clock"
    _attr_native_unit_of_measurement = "min"

    def __init__(self, coordinator, target_user, entry) -> None:
        super().__init__(coordinator, target_user)
        self._attr_unique_id = f"{entry.entry_id}_time_spent_week"
        self._attr_name = "Temps utilis\u00e9 cette semaine"

    @property
    def native_value(self) -> int | None:
        seconds = self.coordinator.data.get("time_spent_week")
        if seconds is not None:
            return seconds // 60
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        seconds = self.coordinator.data.get("time_spent_week")
        if seconds is not None:
            h, remainder = divmod(seconds, 3600)
            m = remainder // 60
            attrs["formatted"] = f"{h}h{m:02d}"
            attrs["seconds"] = seconds
        return attrs


# ── Status sensors ─────────────────────────────────────────────────


class TimekpraOnlineSensor(TimekpraEntity, SensorEntity):
    """Shows whether the child's computer is reachable."""

    _attr_icon = "mdi:desktop-classic"

    def __init__(self, coordinator, target_user, entry) -> None:
        super().__init__(coordinator, target_user)
        self._attr_unique_id = f"{entry.entry_id}_online"
        self._attr_name = "Ordinateur"

    @property
    def native_value(self) -> str:
        if self.coordinator.data.get("online"):
            return "En ligne"
        return "Hors ligne"

    @property
    def icon(self) -> str:
        if self.coordinator.data.get("online"):
            return "mdi:desktop-classic"
        return "mdi:desktop-classic-off"


class TimekpraPendingSensor(TimekpraEntity, SensorEntity):
    """Shows the number of queued changes waiting to be applied."""

    _attr_icon = "mdi:cloud-upload-outline"
    _attr_native_unit_of_measurement = "modification(s)"

    def __init__(self, coordinator, target_user, entry) -> None:
        super().__init__(coordinator, target_user)
        self._attr_unique_id = f"{entry.entry_id}_pending"
        self._attr_name = "Modifications en attente"

    @property
    def native_value(self) -> int:
        return self.coordinator.data.get("pending_count", 0)

    @property
    def icon(self) -> str:
        if self.coordinator.data.get("pending_count", 0) > 0:
            return "mdi:cloud-sync"
        return "mdi:cloud-check"
