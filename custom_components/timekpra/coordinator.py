"""Data update coordinator for Timekpra with offline command queue."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import asyncssh

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SCAN_INTERVAL_SECONDS, DEFAULT_NOTIFICATION_THRESHOLD
from .ssh import TimekpraSSH

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 2


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
            await self._save_state()
        except Exception:
            _LOGGER.exception("Unexpected error running %s", method)
            self._pending[method] = full_args
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

        hours: list[int] = []
        for key in ("ALLOWED_HOURS_ALL", "ALLOWED_HOURS_1", "ALLOWED_HOURS_MON"):
            if key in raw:
                hours = [
                    int(h) for h in raw[key].split(";") if h.strip().isdigit()
                ]
                break
        data["hour_start"] = min(hours) if hours else 0
        data["hour_end"] = max(hours) if hours else 23

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
