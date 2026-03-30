"""Data update coordinator for Timekpra with offline command queue."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any

import asyncssh

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DEFAULT_NOTIFICATION_THRESHOLD,
    DEFAULT_PROFILES,
    DOMAIN,
    PROFILE_CUSTOM,
    PROFILE_OVERRIDE,
    SCAN_INTERVAL_SECONDS,
    UNLIMITED_DAILY,
    UNLIMITED_MONTHLY,
    UNLIMITED_WEEKLY,
)
from .ssh import TimekpraSSH

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 2

_HOUR_RE = re.compile(r"^!?(\d+)(?:\[(\d+)-(\d+)\])?$")


def _parse_hour_entries(raw: str) -> list[tuple[int, int, int]]:
    """Parse timekpra hour string into (hour, minute_start, minute_end) tuples.

    Examples: ``"7[30-59];8;9;20[00-45]"`` →
    ``[(7,30,59), (8,0,59), (9,0,59), (20,0,45)]``
    """
    results: list[tuple[int, int, int]] = []
    if not raw:
        return results
    for entry in raw.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        m = _HOUR_RE.match(entry)
        if m:
            h = int(m.group(1))
            ms = int(m.group(2)) if m.group(2) is not None else 0
            me = int(m.group(3)) if m.group(3) is not None else 59
            results.append((h, ms, me))
    return results


class TimekpraCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch Timekpra config and queue commands when the machine is offline."""

    def __init__(
        self,
        hass: HomeAssistant,
        ssh: TimekpraSSH,
        target_user: str,
        host: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self.ssh = ssh
        self.target_user = target_user
        # Store key based on host+user (stable across reinstalls)
        store_key = f"{DOMAIN}_state_{host}_{target_user}"
        self._store = Store(hass, STORAGE_VERSION, store_key)
        self._pending: dict[str, list] = {}
        self.saved_values: dict[str, Any] = {}
        self._last_known_data: dict[str, Any] | None = None

    # ── Persistent storage ──────────────────────────────────────────

    async def async_load_pending(self) -> None:
        """Load state from disk: pending commands, saved values, last data."""
        raw = await self._store.async_load()
        if not isinstance(raw, dict):
            return

        self._pending = raw.get("pending", {})
        self.saved_values = raw.get("saved_values", {})
        self._last_known_data = raw.get("last_known_data")

        if self._pending:
            _LOGGER.info(
                "Loaded %d pending command(s) from storage",
                len(self._pending),
            )
        if self._last_known_data:
            _LOGGER.debug("Loaded last known config from storage")

    async def _save_state(self) -> None:
        """Persist everything to disk."""
        await self._store.async_save({
            "pending": dict(self._pending),
            "saved_values": dict(self.saved_values),
            "last_known_data": self._last_known_data,
        })

    async def async_apply(self, method: str, *args: Any) -> None:
        """Execute a timekpra setter, queuing it if the machine is offline.

        Only the latest call per method is kept (last-write-wins).
        ``target_user`` is prepended automatically.
        """
        full_args: list = [self.target_user, *args]
        try:
            await getattr(self.ssh, method)(*full_args)
            # Success – remove from queue if it was there
            if method in self._pending:
                del self._pending[method]
                await self._save_state()
        except (OSError, asyncssh.Error):
            _LOGGER.info("Machine offline - queuing %s for later", method)
            self._pending[method] = full_args
            # Persist current in-memory data so changes survive HA restart
            if self.data:
                self._last_known_data = dict(self.data)
            await self._save_state()
        except Exception:
            _LOGGER.exception("Unexpected error running %s", method)
            self._pending[method] = full_args
            if self.data:
                self._last_known_data = dict(self.data)
            await self._save_state()

    async def _flush_pending(self) -> None:
        """Replay every queued command. Stops on first connection error."""
        if not self._pending:
            return
        flushed: list[str] = []
        for method, args in self._pending.items():
            try:
                await getattr(self.ssh, method)(*args)
                flushed.append(method)
                _LOGGER.info("Flushed pending command: %s", method)
            except (OSError, asyncssh.Error):
                _LOGGER.debug("Still offline, stopping flush")
                break
            except Exception:
                _LOGGER.warning("Dropping bad queued command: %s", method)
                flushed.append(method)
        if flushed:
            for m in flushed:
                self._pending.pop(m, None)
            await self._save_state()

    async def async_save_state(self) -> None:
        """Persist saved_values (called by limit-toggle switches)."""
        await self._save_state()

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    # ── Profiles ───────────────────────────────────────────────────

    _PROFILE_KEYS = (
        "allowed_days",
        "hour_start",
        "hour_end",
        "minute_start",
        "minute_end",
        "daily_limits",
        "weekly_limit",
        "monthly_limit",
        "track_inactive",
        "lockout_type",
    )

    @property
    def profiles(self) -> dict[str, dict[str, Any]]:
        """Return merged default + user profiles, minus deleted defaults."""
        deleted = set(self.saved_values.get("deleted_profiles", []))
        user_profiles = self.saved_values.get("profiles", {})
        merged = {k: v for k, v in DEFAULT_PROFILES.items() if k not in deleted}
        merged.update(user_profiles)
        return merged

    @property
    def profile_names(self) -> list[str]:
        """Ordered list: Personnalisé + sorted profiles + Déblocage temporaire."""
        return [PROFILE_CUSTOM] + sorted(self.profiles.keys()) + [PROFILE_OVERRIDE]

    @property
    def active_profile(self) -> str:
        return self.saved_values.get("active_profile", PROFILE_CUSTOM)

    async def async_save_profile(self, name: str) -> None:
        """Save current settings as a named profile."""
        if name == PROFILE_OVERRIDE:
            _LOGGER.warning("Cannot save over built-in profile: %s", name)
            return
        if not self.data:
            return
        snapshot = {k: self.data[k] for k in self._PROFILE_KEYS if k in self.data}
        if "daily_limits" in snapshot:
            snapshot["daily_limits"] = list(snapshot["daily_limits"])
        if "allowed_days" in snapshot:
            snapshot["allowed_days"] = list(snapshot["allowed_days"])
        user_profiles = self.saved_values.setdefault("profiles", {})
        user_profiles[name] = snapshot
        self.saved_values["active_profile"] = name
        # Re-enable if it was previously deleted
        deleted = self.saved_values.get("deleted_profiles", [])
        if name in deleted:
            deleted.remove(name)
        await self._save_state()
        self.async_update_listeners()
        _LOGGER.info("Saved profile: %s", name)

    async def async_delete_profile(self, name: str) -> None:
        """Delete a profile (cannot delete override or Personnalisé)."""
        if name in (PROFILE_OVERRIDE, PROFILE_CUSTOM):
            _LOGGER.warning("Cannot delete built-in profile: %s", name)
            return
        user_profiles = self.saved_values.get("profiles", {})
        if name in user_profiles:
            del user_profiles[name]
        if name in DEFAULT_PROFILES:
            deleted = self.saved_values.setdefault("deleted_profiles", [])
            if name not in deleted:
                deleted.append(name)
        if self.saved_values.get("active_profile") == name:
            self.saved_values["active_profile"] = PROFILE_CUSTOM
        await self._save_state()
        self.async_update_listeners()
        _LOGGER.info("Deleted profile: %s", name)

    async def async_apply_profile(self, name: str) -> None:
        """Load a profile and apply all its settings to timekpra."""
        if name == PROFILE_CUSTOM:
            self.saved_values["active_profile"] = PROFILE_CUSTOM
            self.saved_values["override_active"] = False
            await self._save_state()
            return

        data = self.data
        if not data:
            return

        self.saved_values["active_profile"] = name

        if name == PROFILE_OVERRIDE:
            # ── Déblocage temporaire: save current state, set everything unlimited
            self.saved_values["override_active"] = True
            self.saved_values["override_hours"] = {
                "hour_start": data.get("hour_start", 0),
                "hour_end": data.get("hour_end", 23),
                "minute_start": data.get("minute_start", 0),
                "minute_end": data.get("minute_end", 59),
            }
            current_daily = data.get("daily_limits", [60] * 7)
            if any(v < UNLIMITED_DAILY for v in current_daily):
                self.saved_values["override_daily"] = list(current_daily)
            current_weekly = data.get("weekly_limit", 9)
            if current_weekly < UNLIMITED_WEEKLY:
                self.saved_values["override_weekly"] = current_weekly
            current_monthly = data.get("monthly_limit", 40)
            if current_monthly < UNLIMITED_MONTHLY:
                self.saved_values["override_monthly"] = current_monthly
            await self._save_state()

            data["hour_start"] = 0
            data["hour_end"] = 23
            data["minute_start"] = 0
            data["minute_end"] = 59
            data["daily_limits"] = [UNLIMITED_DAILY] * 7
            data["weekly_limit"] = UNLIMITED_WEEKLY
            data["monthly_limit"] = UNLIMITED_MONTHLY

            await self.async_apply("set_allowed_hours", 0, 23, 0, 59)
            await self.async_apply("set_time_limits", [UNLIMITED_DAILY] * 7)
            await self.async_apply("set_time_limit_week", UNLIMITED_WEEKLY)
            await self.async_apply("set_time_limit_month", UNLIMITED_MONTHLY)
            await self.async_apply("set_time_left", "=", 86400)
            _LOGGER.info("Applied profile: %s (override ON)", name)
            return

        # ── Normal profile ─────────────────────────────────────────
        profile = self.profiles.get(name)
        if not profile:
            _LOGGER.warning("Profile not found: %s", name)
            return

        # Disable override if it was active
        self.saved_values["override_active"] = False
        self.saved_values.pop("override_hours", None)
        self.saved_values.pop("override_daily", None)
        self.saved_values.pop("override_weekly", None)
        self.saved_values.pop("override_monthly", None)
        await self._save_state()

        # Apply all profile values to coordinator data
        for key in self._PROFILE_KEYS:
            if key in profile:
                val = profile[key]
                if isinstance(val, list):
                    val = list(val)
                data[key] = val

        # Push settings to remote machine
        await self.async_apply(
            "set_allowed_days",
            profile.get("allowed_days", data.get("allowed_days", [1, 2, 3, 4, 5, 6, 7])),
        )
        await self.async_apply(
            "set_allowed_hours",
            profile.get("hour_start", 0),
            profile.get("hour_end", 23),
            profile.get("minute_start", 0),
            profile.get("minute_end", 59),
        )
        await self.async_apply(
            "set_time_limits",
            list(profile.get("daily_limits", [60] * 7)),
        )
        await self.async_apply(
            "set_time_limit_week",
            profile.get("weekly_limit", 9),
        )
        await self.async_apply(
            "set_time_limit_month",
            profile.get("monthly_limit", 40),
        )
        await self.async_apply(
            "set_track_inactive",
            profile.get("track_inactive", False),
        )
        await self.async_apply(
            "set_lockout_type",
            profile.get("lockout_type", "lock"),
        )
        _LOGGER.info("Applied profile: %s", name)

    # ── Coordinator refresh ────────────────────────────────────────

    async def _async_update_data(self) -> dict[str, Any]:
        """Pull config from the remote machine.

        Never raises so the integration stays loaded even when the
        child's computer is turned off.
        """
        # 1. Try to flush any queued commands
        await self._flush_pending()

        # 2. Try to read current config
        online = False
        raw_config: dict[str, str] | None = None
        try:
            raw_config = await self.ssh.get_config(self.target_user)
            if raw_config is not None:
                online = True
        except Exception:
            _LOGGER.debug("Cannot reach machine for config read")

        # 3. Build data (priority: live > previous > stored > defaults)
        if raw_config is not None:
            data = self._process_config(raw_config)
            # Save as last known good data
            self._last_known_data = dict(data)
            await self._save_state()
        elif self.data:
            # Still in memory from a previous refresh
            data = dict(self.data)
        elif self._last_known_data:
            # Restored from disk after HA restart
            data = dict(self._last_known_data)
            _LOGGER.debug("Using last known config from storage")
        else:
            data = self._default_data()

        data["online"] = online
        data["pending_count"] = self.pending_count

        # 4. Best-effort: time tracking
        if online:
            try:
                time_data = await self.ssh.get_time_spent(self.target_user)
                if time_data:
                    data.update(self._process_time_data(time_data))
            except Exception:
                pass

        # 5. Calculate time remaining today
        data["time_remaining"] = self._calc_time_remaining(data)

        # 6. Notification threshold from saved_values
        data["notification_threshold"] = self.saved_values.get(
            "notification_threshold", DEFAULT_NOTIFICATION_THRESHOLD
        )

        return data

    # ── Parsers ────────────────────────────────────────────────────

    @staticmethod
    def _default_data() -> dict[str, Any]:
        """Safe defaults when no remote data is available yet."""
        return {
            "allowed_days": [1, 2, 3, 4, 5, 6, 7],
            "hour_start": 0,
            "hour_end": 23,
            "minute_start": 0,
            "minute_end": 59,
            "daily_limits": [60] * 7,
            "weekly_limit": 0,
            "monthly_limit": 0,
            "track_inactive": False,
            "lockout_type": "lock",
            "online": False,
            "pending_count": 0,
            "time_remaining": None,
            "notification_threshold": DEFAULT_NOTIFICATION_THRESHOLD,
        }

    @staticmethod
    def _calc_time_remaining(data: dict[str, Any]) -> int | None:
        """Calculate seconds remaining today (daily limit - time spent)."""
        time_spent = data.get("time_spent_today")
        if time_spent is None:
            return None
        daily_limits = data.get("daily_limits", [])
        # Monday=0 in Python, day index in DAYS is 0-based
        day_index = datetime.now().weekday()
        if day_index >= len(daily_limits):
            return None
        limit_minutes = daily_limits[day_index]
        limit_seconds = limit_minutes * 60
        remaining = limit_seconds - time_spent
        return max(0, remaining)

    @staticmethod
    def _process_config(raw: dict[str, str]) -> dict[str, Any]:
        """Transform raw key=value pairs into structured data."""
        data: dict[str, Any] = {}

        days_str = raw.get("ALLOWED_WEEKDAYS", "")
        days = [int(d) for d in days_str.split(";") if d.strip().isdigit()]
        data["allowed_days"] = days if days else [1, 2, 3, 4, 5, 6, 7]

        hours_raw: str = ""
        for key in ("ALLOWED_HOURS_ALL", "ALLOWED_HOURS_1", "ALLOWED_HOURS_MON"):
            if key in raw:
                hours_raw = raw[key]
                break

        hour_entries = _parse_hour_entries(hours_raw)
        hours = [e[0] for e in hour_entries]
        data["hour_start"] = min(hours) if hours else 0
        data["hour_end"] = max(hours) if hours else 23
        # Minutes from first and last entry brackets
        data["minute_start"] = hour_entries[0][1] if hour_entries else 0
        data["minute_end"] = hour_entries[-1][2] if hour_entries else 59

        limits_str = raw.get("LIMITS_PER_WEEKDAYS", "")
        if limits_str:
            data["daily_limits"] = [
                int(s) // 60
                for s in limits_str.split(";")
                if s.strip().isdigit()
            ]
        else:
            data["daily_limits"] = [60] * 7
        while len(data["daily_limits"]) < 7:
            data["daily_limits"].append(60)

        try:
            data["weekly_limit"] = int(raw.get("LIMIT_PER_WEEK", "0")) // 3600
        except ValueError:
            data["weekly_limit"] = 0

        try:
            data["monthly_limit"] = int(raw.get("LIMIT_PER_MONTH", "0")) // 3600
        except ValueError:
            data["monthly_limit"] = 0

        data["track_inactive"] = (
            raw.get("TRACK_INACTIVE", "False").lower() == "true"
        )
        data["lockout_type"] = raw.get("LOCKOUT_TYPE", "lock").lower()

        return data

    @staticmethod
    def _process_time_data(raw: dict[str, str]) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for key in ("TIME_SPENT_DAY", "TIME_SPENT_TODAY", "SECONDS_SPENT"):
            if key in raw:
                try:
                    data["time_spent_today"] = int(raw[key])
                except (ValueError, TypeError):
                    pass
                break
        for key in ("TIME_SPENT_WEEK",):
            if key in raw:
                try:
                    data["time_spent_week"] = int(raw[key])
                except (ValueError, TypeError):
                    pass
                break
        return data
