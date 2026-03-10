"""Switch entities for the Timekpra integration."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DAYS, DOMAIN
from .coordinator import TimekpraCoordinator
from .entity import TimekpraEntity
from .ssh import TimekpraSSH

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Timekpra switch entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: TimekpraCoordinator = data["coordinator"]
    ssh: TimekpraSSH = data["ssh"]
    target_user: str = data["target_user"]

    entities: list[SwitchEntity] = []

    # One switch per weekday
    for idx, day in enumerate(DAYS):
        entities.append(
            TimekpraDaySwitch(coordinator, ssh, target_user, day, entry)
        )

    # Track-inactive toggle
    entities.append(
        TimekpraTrackInactiveSwitch(coordinator, ssh, target_user, entry)
    )

    async_add_entities(entities)


# ── Day switches ───────────────────────────────────────────────────


class TimekpraDaySwitch(TimekpraEntity, SwitchEntity):
    """Toggle whether a given weekday is allowed."""

    _attr_icon = "mdi:calendar"

    def __init__(self, coordinator, ssh, target_user, day, entry) -> None:
        super().__init__(coordinator, target_user)
        self._ssh = ssh
        self._day_number = day["number"]
        self._attr_unique_id = f"{entry.entry_id}_day_{day['key']}"
        self._attr_name = f"Jour autoris\u00e9 - {day['name']}"

    @property
    def is_on(self) -> bool | None:
        return self._day_number in self.coordinator.data.get("allowed_days", [])

    async def _set_days(self, add: bool) -> None:
        days = set(self.coordinator.data.get("allowed_days", []))
        if add:
            days.add(self._day_number)
        else:
            days.discard(self._day_number)
        sorted_days = sorted(days)
        self.coordinator.data["allowed_days"] = sorted_days
        self.async_write_ha_state()
        await self.coordinator.async_apply("set_allowed_days", sorted_days)

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_days(add=True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_days(add=False)


# ── Track inactive ─────────────────────────────────────────────────


class TimekpraTrackInactiveSwitch(TimekpraEntity, SwitchEntity):
    """Toggle whether idle/inactive time is counted."""

    _attr_icon = "mdi:sleep"

    def __init__(self, coordinator, ssh, target_user, entry) -> None:
        super().__init__(coordinator, target_user)
        self._ssh = ssh
        self._attr_unique_id = f"{entry.entry_id}_track_inactive"
        self._attr_name = "Compter le temps inactif"

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get("track_inactive")

    async def async_turn_on(self, **kwargs) -> None:
        self.coordinator.data["track_inactive"] = True
        self.async_write_ha_state()
        await self.coordinator.async_apply("set_track_inactive", True)

    async def async_turn_off(self, **kwargs) -> None:
        self.coordinator.data["track_inactive"] = False
        self.async_write_ha_state()
        await self.coordinator.async_apply("set_track_inactive", False)
