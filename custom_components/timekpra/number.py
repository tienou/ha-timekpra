"""Number entities for the Timekpra integration."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DAYS, DEFAULT_NOTIFICATION_THRESHOLD, DOMAIN
from .coordinator import TimekpraCoordinator
from .entity import TimekpraEntity
from .ssh import TimekpraSSH

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Timekpra number entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: TimekpraCoordinator = data["coordinator"]
    ssh: TimekpraSSH = data["ssh"]
    target_user: str = data["target_user"]

    entities: list[NumberEntity] = []

    # Per-day time limits
    for idx, day in enumerate(DAYS):
        entities.append(
            TimekpraDailyLimit(coordinator, ssh, target_user, idx, day, entry)
        )

    # Weekly / monthly limits
    entities.append(TimekpraWeeklyLimit(coordinator, ssh, target_user, entry))
    entities.append(TimekpraMonthlyLimit(coordinator, ssh, target_user, entry))

    # Allowed-hours range (hours + minutes)
    entities.append(TimekpraHourStart(coordinator, ssh, target_user, entry))
    entities.append(TimekpraMinuteStart(coordinator, ssh, target_user, entry))
    entities.append(TimekpraHourEnd(coordinator, ssh, target_user, entry))
    entities.append(TimekpraMinuteEnd(coordinator, ssh, target_user, entry))

    # Notification threshold
    entities.append(TimekpraNotificationThreshold(coordinator, target_user, entry))

    async_add_entities(entities)


# ── Daily limits ───────────────────────────────────────────────────


class TimekpraDailyLimit(TimekpraEntity, NumberEntity):
    """Slider for per-day time limit (in minutes)."""

    _attr_native_min_value = 0
    _attr_native_max_value = 1440
    _attr_native_step = 15
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:timer-outline"

    def __init__(
        self,
        coordinator: TimekpraCoordinator,
        ssh: TimekpraSSH,
        target_user: str,
        day_index: int,
        day: dict,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, target_user)
        self._ssh = ssh
        self._day_index = day_index
        self._attr_unique_id = f"{entry.entry_id}_limit_{day['key']}"
        self._attr_name = f"Limite {day['name']}"

    @property
    def native_value(self) -> float | None:
        limits = self.coordinator.data.get("daily_limits", [])
        if self._day_index < len(limits):
            return limits[self._day_index]
        return None

    async def async_set_native_value(self, value: float) -> None:
        limits = list(self.coordinator.data.get("daily_limits", [60] * 7))
        limits[self._day_index] = int(value)
        self.coordinator.data["daily_limits"] = limits
        self.async_write_ha_state()
        await self.coordinator.async_apply("set_time_limits", limits)


# ── Weekly limit ───────────────────────────────────────────────────


class TimekpraWeeklyLimit(TimekpraEntity, NumberEntity):
    """Box input for weekly time limit (in hours)."""

    _attr_native_min_value = 0
    _attr_native_max_value = 168
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "h"
    _attr_icon = "mdi:calendar-week"

    def __init__(self, coordinator, ssh, target_user, entry) -> None:
        super().__init__(coordinator, target_user)
        self._ssh = ssh
        self._attr_unique_id = f"{entry.entry_id}_limit_week"
        self._attr_name = "Limite hebdomadaire"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("weekly_limit")

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.data["weekly_limit"] = int(value)
        self.async_write_ha_state()
        await self.coordinator.async_apply("set_time_limit_week", int(value))


# ── Monthly limit ──────────────────────────────────────────────────


class TimekpraMonthlyLimit(TimekpraEntity, NumberEntity):
    """Box input for monthly time limit (in hours)."""

    _attr_native_min_value = 0
    _attr_native_max_value = 744
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "h"
    _attr_icon = "mdi:calendar-month"

    def __init__(self, coordinator, ssh, target_user, entry) -> None:
        super().__init__(coordinator, target_user)
        self._ssh = ssh
        self._attr_unique_id = f"{entry.entry_id}_limit_month"
        self._attr_name = "Limite mensuelle"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("monthly_limit")

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.data["monthly_limit"] = int(value)
        self.async_write_ha_state()
        await self.coordinator.async_apply("set_time_limit_month", int(value))


# ── Hour range ─────────────────────────────────────────────────────


class TimekpraHourStart(TimekpraEntity, NumberEntity):
    """Box for the earliest allowed login hour."""

    _attr_native_min_value = 0
    _attr_native_max_value = 23
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "h"
    _attr_icon = "mdi:clock-start"

    def __init__(self, coordinator, ssh, target_user, entry) -> None:
        super().__init__(coordinator, target_user)
        self._ssh = ssh
        self._attr_unique_id = f"{entry.entry_id}_hour_start"
        self._attr_name = "Heure de d\u00e9but"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("hour_start")

    async def async_set_native_value(self, value: float) -> None:
        hour_end = self.coordinator.data.get("hour_end", 23)
        minute_start = self.coordinator.data.get("minute_start", 0)
        minute_end = self.coordinator.data.get("minute_end", 59)
        self.coordinator.data["hour_start"] = int(value)
        self.async_write_ha_state()
        await self.coordinator.async_apply(
            "set_allowed_hours", int(value), hour_end, minute_start, minute_end
        )


class TimekpraMinuteStart(TimekpraEntity, NumberEntity):
    """Box for the start minute of the first allowed hour."""

    _attr_native_min_value = 0
    _attr_native_max_value = 55
    _attr_native_step = 5
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:clock-start"

    def __init__(self, coordinator, ssh, target_user, entry) -> None:
        super().__init__(coordinator, target_user)
        self._ssh = ssh
        self._attr_unique_id = f"{entry.entry_id}_minute_start"
        self._attr_name = "Minute de d\u00e9but"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("minute_start", 0)

    async def async_set_native_value(self, value: float) -> None:
        hour_start = self.coordinator.data.get("hour_start", 0)
        hour_end = self.coordinator.data.get("hour_end", 23)
        minute_end = self.coordinator.data.get("minute_end", 59)
        self.coordinator.data["minute_start"] = int(value)
        self.async_write_ha_state()
        await self.coordinator.async_apply(
            "set_allowed_hours", hour_start, hour_end, int(value), minute_end
        )


class TimekpraHourEnd(TimekpraEntity, NumberEntity):
    """Box for the latest allowed login hour."""

    _attr_native_min_value = 0
    _attr_native_max_value = 23
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "h"
    _attr_icon = "mdi:clock-end"

    def __init__(self, coordinator, ssh, target_user, entry) -> None:
        super().__init__(coordinator, target_user)
        self._ssh = ssh
        self._attr_unique_id = f"{entry.entry_id}_hour_end"
        self._attr_name = "Heure de fin"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("hour_end")

    async def async_set_native_value(self, value: float) -> None:
        hour_start = self.coordinator.data.get("hour_start", 0)
        minute_start = self.coordinator.data.get("minute_start", 0)
        minute_end = self.coordinator.data.get("minute_end", 59)
        self.coordinator.data["hour_end"] = int(value)
        self.async_write_ha_state()
        await self.coordinator.async_apply(
            "set_allowed_hours", hour_start, int(value), minute_start, minute_end
        )


class TimekpraMinuteEnd(TimekpraEntity, NumberEntity):
    """Box for the end minute of the last allowed hour."""

    _attr_native_min_value = 0
    _attr_native_max_value = 55
    _attr_native_step = 5
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:clock-end"

    def __init__(self, coordinator, ssh, target_user, entry) -> None:
        super().__init__(coordinator, target_user)
        self._ssh = ssh
        self._attr_unique_id = f"{entry.entry_id}_minute_end"
        self._attr_name = "Minute de fin"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("minute_end", 59)

    async def async_set_native_value(self, value: float) -> None:
        hour_start = self.coordinator.data.get("hour_start", 0)
        hour_end = self.coordinator.data.get("hour_end", 23)
        minute_start = self.coordinator.data.get("minute_start", 0)
        self.coordinator.data["minute_end"] = int(value)
        self.async_write_ha_state()
        await self.coordinator.async_apply(
            "set_allowed_hours", hour_start, hour_end, minute_start, int(value)
        )


# ── Notification threshold ────────────────────────────────────────


class TimekpraNotificationThreshold(TimekpraEntity, NumberEntity):
    """Box for notification threshold before lock (in minutes, stored locally)."""

    _attr_native_min_value = 0
    _attr_native_max_value = 60
    _attr_native_step = 5
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "min"
    _attr_icon = "mdi:bell-ring-outline"

    def __init__(self, coordinator, target_user, entry) -> None:
        super().__init__(coordinator, target_user)
        self._attr_unique_id = f"{entry.entry_id}_notification_threshold"
        self._attr_name = "Notification avant verrouillage"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get(
            "notification_threshold", DEFAULT_NOTIFICATION_THRESHOLD
        )

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.data["notification_threshold"] = int(value)
        self.coordinator.saved_values["notification_threshold"] = int(value)
        self.async_write_ha_state()
        await self.coordinator.async_save_state()
