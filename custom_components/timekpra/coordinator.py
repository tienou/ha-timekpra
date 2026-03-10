"""Data update coordinator for Timekpra with offline command queue."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import asyncssh

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SCAN_INTERVAL_SECONDS
from .ssh import TimekpraSSH

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


class TimekpraCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch Timekpra config and queue commands when the machine is offline."""

    def __init__(
        self,
        hass: HomeAssistant,
        ssh: TimekpraSSH,
        target_user: str,
        entry_id: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self.ssh = ssh
        self.target_user = target_user
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_pending_{entry_id}")
        self._pending: dict[str, list] = {}

    # ── Persistent queue ───────────────────────────────────────────

    async def async_load_pending(self) -> None:
        """Load queued commands from disk (call once at startup)."""
        data = await self._store.async_load()
        if isinstance(data, dict):
            self._pending = data
            if self._pending:
                _LOGGER.info(
                    "Loaded %d pending command(s) from storage",
                    len(self._pending),
                )

    async def _save_pending(self) -> None:
        """Persist the current queue to disk."""
        await self._store.async_save(dict(self._pending))

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
                await self._save_pending()
        except (OSError, asyncssh.Error):
            _LOGGER.info("Machine offline - queuing %s for later", method)
            self._pending[method] = full_args
            await self._save_pending()
        except Exception:
            _LOGGER.exception("Unexpected error running %s", method)
            self._pending[method] = full_args
            await self._save_pending()

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
            await self._save_pending()

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

        # 3. Build data
        if raw_config is not None:
            data = self._process_config(raw_config)
        elif self.data:
            data = dict(self.data)
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
        }

    @staticmethod
    def _process_config(raw: dict[str, str]) -> dict[str, Any]:
        """Transform raw key=value pairs into structured data."""
        data: dict[str, Any] = {}

        days_str = raw.get("ALLOWED_WEEKDAYS", "1;2;3;4;5;6;7")
        data["allowed_days"] = [
            int(d) for d in days_str.split(";") if d.strip().isdigit()
        ]

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
