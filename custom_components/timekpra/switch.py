"""Switch entities for the Timekpra integration."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DAYS,
    DEFAULT_DAILY_LIMITS,
    DEFAULT_MONTHLY_LIMIT,
    DEFAULT_WEEKLY_LIMIT,
    DOMAIN,
    PROFILE_CUSTOM,
    PROFILE_OVERRIDE,
    UNLIMITED_DAILY,
    UNLIMITED_MONTHLY,
    UNLIMITED_WEEKLY,
)
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

    # Limit enable/disable toggles
    entities.append(TimekpraDailyLimitToggle(coordinator, target_user, entry))
    entities.append(TimekpraWeeklyLimitToggle(coordinator, target_user, entry))
    entities.append(TimekpraMonthlyLimitToggle(coordinator, target_user, entry))

    # Temporary override (bypass ALL restrictions)
    entities.append(TimekpraOverrideSwitch(coordinator, target_user, entry))

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


# ── Limit toggles ─────────────────────────────────────────────────


class TimekpraDailyLimitToggle(TimekpraEntity, SwitchEntity):
    """Toggle daily time limits on/off.

    OFF = sets all days to 24 h (unlimited).
    ON  = restores previously saved values.
    """

    _attr_icon = "mdi:timer-check-outline"

    def __init__(self, coordinator, target_user, entry) -> None:
        super().__init__(coordinator, target_user)
        self._attr_unique_id = f"{entry.entry_id}_daily_limit_enabled"
        self._attr_name = "Limites quotidiennes actives"

    @property
    def is_on(self) -> bool:
        limits = self.coordinator.data.get("daily_limits", [])
        return any(v < UNLIMITED_DAILY for v in limits)

    async def async_turn_off(self, **kwargs) -> None:
        # Save current limits before disabling
        current = self.coordinator.data.get("daily_limits", DEFAULT_DAILY_LIMITS)
        if any(v < UNLIMITED_DAILY for v in current):
            self.coordinator.saved_values["daily_limits"] = list(current)
            await self.coordinator.async_save_state()
        unlimited = [UNLIMITED_DAILY] * 7
        self.coordinator.data["daily_limits"] = unlimited
        self.async_write_ha_state()
        await self.coordinator.async_apply("set_time_limits", unlimited)
        # Force 24h de temps restant pour débloquer immédiatement
        await self.coordinator.async_apply("set_time_left", "=", 86400)

    async def async_turn_on(self, **kwargs) -> None:
        restored = self.coordinator.saved_values.get(
            "daily_limits", DEFAULT_DAILY_LIMITS
        )
        self.coordinator.data["daily_limits"] = list(restored)
        self.async_write_ha_state()
        await self.coordinator.async_apply("set_time_limits", list(restored))


class TimekpraWeeklyLimitToggle(TimekpraEntity, SwitchEntity):
    """Toggle weekly time limit on/off."""

    _attr_icon = "mdi:calendar-week-outline"

    def __init__(self, coordinator, target_user, entry) -> None:
        super().__init__(coordinator, target_user)
        self._attr_unique_id = f"{entry.entry_id}_weekly_limit_enabled"
        self._attr_name = "Limite hebdomadaire active"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("weekly_limit", 0) < UNLIMITED_WEEKLY

    async def async_turn_off(self, **kwargs) -> None:
        current = self.coordinator.data.get("weekly_limit", DEFAULT_WEEKLY_LIMIT)
        if current < UNLIMITED_WEEKLY:
            self.coordinator.saved_values["weekly_limit"] = current
            await self.coordinator.async_save_state()
        self.coordinator.data["weekly_limit"] = UNLIMITED_WEEKLY
        self.async_write_ha_state()
        await self.coordinator.async_apply("set_time_limit_week", UNLIMITED_WEEKLY)

    async def async_turn_on(self, **kwargs) -> None:
        restored = self.coordinator.saved_values.get(
            "weekly_limit", DEFAULT_WEEKLY_LIMIT
        )
        self.coordinator.data["weekly_limit"] = restored
        self.async_write_ha_state()
        await self.coordinator.async_apply("set_time_limit_week", restored)


class TimekpraMonthlyLimitToggle(TimekpraEntity, SwitchEntity):
    """Toggle monthly time limit on/off."""

    _attr_icon = "mdi:calendar-month-outline"

    def __init__(self, coordinator, target_user, entry) -> None:
        super().__init__(coordinator, target_user)
        self._attr_unique_id = f"{entry.entry_id}_monthly_limit_enabled"
        self._attr_name = "Limite mensuelle active"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("monthly_limit", 0) < UNLIMITED_MONTHLY

    async def async_turn_off(self, **kwargs) -> None:
        current = self.coordinator.data.get("monthly_limit", DEFAULT_MONTHLY_LIMIT)
        if current < UNLIMITED_MONTHLY:
            self.coordinator.saved_values["monthly_limit"] = current
            await self.coordinator.async_save_state()
        self.coordinator.data["monthly_limit"] = UNLIMITED_MONTHLY
        self.async_write_ha_state()
        await self.coordinator.async_apply("set_time_limit_month", UNLIMITED_MONTHLY)

    async def async_turn_on(self, **kwargs) -> None:
        restored = self.coordinator.saved_values.get(
            "monthly_limit", DEFAULT_MONTHLY_LIMIT
        )
        self.coordinator.data["monthly_limit"] = restored
        self.async_write_ha_state()
        await self.coordinator.async_apply("set_time_limit_month", restored)


# ── Temporary override (bypass ALL restrictions) ───────────────────


class TimekpraOverrideSwitch(TimekpraEntity, SwitchEntity):
    """Temporarily bypass ALL restrictions via the profile system.

    ON  = selects the 'Déblocage temporaire' profile.
    OFF = reverts to 'Personnalisé' profile.
    """

    _attr_icon = "mdi:shield-off-outline"

    def __init__(self, coordinator, target_user, entry) -> None:
        super().__init__(coordinator, target_user)
        self._attr_unique_id = f"{entry.entry_id}_override"
        self._attr_name = "Déblocage temporaire"

    @property
    def is_on(self) -> bool:
        return self.coordinator.active_profile == PROFILE_OVERRIDE

    async def async_turn_on(self, **kwargs) -> None:
        if self.is_on:
            return
        await self.coordinator.async_apply_profile(PROFILE_OVERRIDE)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        if not self.is_on:
            return
        await self.coordinator.async_apply_profile(PROFILE_CUSTOM)
        self.async_write_ha_state()
