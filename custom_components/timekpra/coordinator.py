"""Data update coordinator for Timekpra with offline command queue."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import asyncssh

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_SSH_HOST,
    CONF_TARGET_USER,
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
from .ssh import TimekpraCommandError, TimekpraSSH
from .timekpr_data import (
    ALL_DAYS,
    align_limits_for_timekpr,
    is_valid_config,
    process_config,
    roll_over_stale_time,
    time_values_from_control,
    time_values_from_userinfo,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 2

# Legacy (French) profile ids → new snake_case ids. Profile ids are now
# snake_case so built-in profiles can be translated via select state
# translations; this remaps any state persisted before that change.
_LEGACY_PROFILE_IDS = {
    "Personnalisé": "custom",
    "Déblocage temporaire": "override",
    "École": "school",
    "Vacances": "holidays",
    "Chez Papi Mamie": "grandparents",
}


class TimekpraCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch Timekpra config and queue commands when the machine is offline."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        ssh: TimekpraSSH,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
            always_update=False,
        )
        self.ssh = ssh
        self.target_user = entry.data[CONF_TARGET_USER]
        # Store key based on host+user (stable across reinstalls)
        store_key = f"{DOMAIN}_state_{entry.data[CONF_SSH_HOST]}_{self.target_user}"
        self._store = Store(hass, STORAGE_VERSION, store_key)
        self._pending: dict[str, list] = {}
        self.saved_values: dict[str, Any] = {}
        self._last_known_data: dict[str, Any] | None = None

    async def _async_setup(self) -> None:
        """Run once during async_config_entry_first_refresh: load persisted
        state and wire host-key pinning before the first connection."""
        await self.async_load_pending()

    # ── Persistent storage ──────────────────────────────────────────

    async def async_load_pending(self) -> None:
        """Load state from disk: pending commands, saved values, last data."""
        raw = await self._store.async_load()
        if isinstance(raw, dict):
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

            if self._migrate_legacy_profile_ids():
                await self._save_state()

        # Wire SSH host-key pinning (TOFU) — must run even on a fresh install
        # so the first connection's key gets persisted.
        self.ssh.set_host_key(self.saved_values.get("host_key", ""))
        self.ssh.host_key_saver = self._save_host_key

    async def _save_host_key(self, key_str: str) -> None:
        """Persist the pinned SSH host key learned on first connect (TOFU)."""
        self.saved_values["host_key"] = key_str
        await self._save_state()

    def _migrate_legacy_profile_ids(self) -> bool:
        """Rewrite legacy French profile ids to snake_case. Returns True if changed."""
        changed = False

        active = self.saved_values.get("active_profile")
        if active in _LEGACY_PROFILE_IDS:
            self.saved_values["active_profile"] = _LEGACY_PROFILE_IDS[active]
            changed = True

        deleted = self.saved_values.get("deleted_profiles")
        if isinstance(deleted, list):
            migrated = [_LEGACY_PROFILE_IDS.get(name, name) for name in deleted]
            if migrated != deleted:
                self.saved_values["deleted_profiles"] = migrated
                changed = True

        # Rename any user-saved profile stored under a legacy default id.
        profiles = self.saved_values.get("profiles")
        if isinstance(profiles, dict):
            for old_id, new_id in _LEGACY_PROFILE_IDS.items():
                if old_id not in profiles:
                    continue
                snapshot = profiles.pop(old_id)
                changed = True
                # A user profile saved as "Personnalisé" / "Déblocage
                # temporaire" would become the reserved "custom" / "override"
                # id and show up twice in the select; and an existing new id
                # must not be silently overwritten (nor this one dropped).
                if new_id in (PROFILE_CUSTOM, PROFILE_OVERRIDE) or new_id in profiles:
                    profiles[f"{old_id} (1)"] = snapshot
                else:
                    profiles[new_id] = snapshot

        if changed:
            _LOGGER.info("Migrated legacy profile ids to snake_case")
        return changed

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
        except TimekpraCommandError as err:
            # Reached the machine but the command failed (wrong sudo password,
            # missing NOPASSWD rule, or a timekpra error). Never treat this as
            # success: keep it queued so the "pending" sensor flags that the
            # change did NOT take effect, and surface the reason in the log.
            _LOGGER.error("Command %s failed on the machine: %s", method, err)
            self._pending[method] = full_args
            if self.data:
                self._last_known_data = dict(self.data)
            await self._save_state()
        except asyncssh.PermissionDenied as err:
            # Authentication failure (bad password/key): retrying won't help,
            # so don't queue it forever — surface it instead.
            _LOGGER.error(
                "SSH authentication failed running %s (check credentials): %s",
                method, err,
            )
        except (OSError, asyncssh.Error):
            _LOGGER.info("Machine offline - queuing %s for later", method)
            self._pending[method] = full_args
            # Persist current in-memory data so changes survive HA restart
            if self.data:
                self._last_known_data = dict(self.data)
            await self._save_state()
        except ValueError as err:
            # Invalid value (e.g. empty hour range): replaying it later
            # would fail the same way, so never queue it.
            _LOGGER.error("Refusing invalid %s: %s", method, err)
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
        flushed: list[tuple[str, Any]] = []
        # Iterate over a snapshot: a user action (async_apply) may add or
        # remove queued commands while we await the SSH round-trips; mutating
        # the dict during iteration raised RuntimeError and failed the refresh.
        for method, args in list(self._pending.items()):
            try:
                await getattr(self.ssh, method)(*args)
                flushed.append((method, args))
                _LOGGER.info("Flushed pending command: %s", method)
            except (OSError, asyncssh.Error):
                _LOGGER.debug("Still offline, stopping flush")
                break
            except TimekpraCommandError as err:
                _LOGGER.error(
                    "Queued command %s still failing, dropping it: %s", method, err
                )
                flushed.append((method, args))
            except Exception:
                _LOGGER.warning("Dropping bad queued command: %s", method)
                flushed.append((method, args))
        if flushed:
            for m, args in flushed:
                # Only drop what we replayed: a newer value queued for the
                # same setter during the flush must survive.
                if self._pending.get(m) is args:
                    del self._pending[m]
            await self._save_state()

    async def async_save_state(self) -> None:
        """Persist saved_values (called by limit-toggle switches)."""
        await self._save_state()

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def timekpr_limits(
        self, daily_limits: list[int], allowed_days: list[int] | None = None
    ) -> list[int]:
        """Daily limits (Mon…Sun, minutes) in the order Timekpr expects.

        Timekpr reads LIMITS_PER_WEEKDAYS positionally on the *allowed* days:
        sending the 7 Monday…Sunday values while a day is disabled shifted
        every following day's limit by one. Defaults to the current days.
        """
        if allowed_days is None:
            allowed_days = (self.data or {}).get("allowed_days", ALL_DAYS)
        return align_limits_for_timekpr(daily_limits, allowed_days)

    async def async_apply_days_and_limits(
        self, allowed_days: list[int], daily_limits: list[int]
    ) -> None:
        """Push allowed days, then the limits re-aligned on those days."""
        async with self.ssh.session():
            await self.async_apply("set_allowed_days", list(allowed_days))
            await self.async_apply(
                "set_time_limits", self.timekpr_limits(daily_limits, allowed_days)
            )

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
        """Ordered list: custom + sorted profiles + override (ids, not labels)."""
        return [PROFILE_CUSTOM] + sorted(self.profiles.keys()) + [PROFILE_OVERRIDE]

    @property
    def active_profile(self) -> str:
        return self.saved_values.get("active_profile", PROFILE_CUSTOM)

    async def async_save_profile(self, name: str) -> None:
        """Save current settings as a named profile."""
        if name in (PROFILE_OVERRIDE, PROFILE_CUSTOM):
            # "custom" too: it would appear twice in the select options.
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
        """Delete a profile (cannot delete the override or custom profile)."""
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

    def _snapshot_before_override(self, data: dict[str, Any]) -> None:
        """Remember the settings to restore when the override ends.

        Only limited settings are saved (a missing key = already unlimited).
        """
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
        # "Bypass ALL restrictions" must also unlock a disallowed day: the
        # override used to leave the day switches untouched, so a child
        # blocked by "no computer on Wednesday" stayed blocked.
        current_days = sorted(data.get("allowed_days", ALL_DAYS))
        if current_days != ALL_DAYS:
            self.saved_values["override_days"] = current_days

    def _consume_override_snapshot(self) -> dict[str, Any]:
        """Pop the pre-override settings to restore when the override ends.

        A missing key means that setting was already unlimited before the
        override, so it is intentionally left as-is (still unlimited).
        """
        restore: dict[str, Any] = {}
        hours = self.saved_values.pop("override_hours", None)
        if hours:
            restore["hour_start"] = hours.get("hour_start", 0)
            restore["hour_end"] = hours.get("hour_end", 23)
            restore["minute_start"] = hours.get("minute_start", 0)
            restore["minute_end"] = hours.get("minute_end", 59)
        daily = self.saved_values.pop("override_daily", None)
        if daily is not None:
            restore["daily_limits"] = list(daily)
        weekly = self.saved_values.pop("override_weekly", None)
        if weekly is not None:
            restore["weekly_limit"] = weekly
        monthly = self.saved_values.pop("override_monthly", None)
        if monthly is not None:
            restore["monthly_limit"] = monthly
        days = self.saved_values.pop("override_days", None)
        if days is not None:
            restore["allowed_days"] = list(days)
        return restore

    async def _push_restore(self, data: dict[str, Any]) -> None:
        """Re-apply restored settings to timekpra after an override ends."""
        async with self.ssh.session():  # one SSH connection for the whole batch
            days = data.get("allowed_days", ALL_DAYS)
            await self.async_apply("set_allowed_days", list(days))
            await self.async_apply(
                "set_allowed_hours",
                data.get("hour_start", 0),
                data.get("hour_end", 23),
                data.get("minute_start", 0),
                data.get("minute_end", 59),
            )
            await self.async_apply(
                "set_time_limits",
                self.timekpr_limits(list(data.get("daily_limits", [60] * 7)), days),
            )
            await self.async_apply("set_time_limit_week", data.get("weekly_limit", 0))
            await self.async_apply("set_time_limit_month", data.get("monthly_limit", 0))
            # The override had granted a full day (set_time_left = 86400). Clamp
            # today's remaining time back to the restored daily limit so the
            # machine is re-enforced now instead of staying unlocked until midnight.
            daily = data.get("daily_limits", [])
            today = dt_util.now().weekday()
            if today < len(daily):
                await self.async_apply("set_time_left", "=", int(daily[today]) * 60)

    async def async_apply_profile(self, name: str) -> None:
        """Load a profile and apply all its settings to timekpra."""
        if name == PROFILE_CUSTOM:
            self.saved_values["active_profile"] = PROFILE_CUSTOM
            self.saved_values["override_active"] = False

            # If a temporary override was active, restore the settings saved
            # before it. Without this, turning the override OFF would silently
            # leave the machine unrestricted (issue #1).
            restore = self._consume_override_snapshot() if self.data else {}
            if restore:
                data = self.data
                for key, val in restore.items():
                    data[key] = list(val) if isinstance(val, list) else val
                await self._save_state()
                # Update the UI immediately, push to the machine in background.
                self.async_set_updated_data(data)
                self.hass.async_create_task(self._push_restore(dict(data)))
                _LOGGER.info("Override OFF — restored previous limits")
                return

            await self._save_state()
            # Use async_set_updated_data to atomically set data + notify
            # (avoids race with periodic _async_update_data replacing self.data)
            if self.data:
                self.async_set_updated_data(self.data)
            else:
                self.async_update_listeners()
            return

        data = self.data
        if not data:
            return

        self.saved_values["active_profile"] = name

        if name == PROFILE_OVERRIDE:
            # ── override: save current state, set everything unlimited
            # Selecting it again while already active must NOT re-snapshot:
            # the current values are then the unlimited ones, and the real
            # pre-override settings would be lost (hours restored as 0h-23h59).
            if not self.saved_values.get("override_active"):
                self._snapshot_before_override(data)
            self.saved_values["override_active"] = True
            await self._save_state()

            data["hour_start"] = 0
            data["hour_end"] = 23
            data["minute_start"] = 0
            data["minute_end"] = 59
            data["daily_limits"] = [UNLIMITED_DAILY] * 7
            data["weekly_limit"] = UNLIMITED_WEEKLY
            data["monthly_limit"] = UNLIMITED_MONTHLY
            data["allowed_days"] = list(ALL_DAYS)

            # Update UI immediately, then push SSH commands in background
            self.async_set_updated_data(data)
            _LOGGER.info("Applied profile: %s (override ON)", name)

            async def _push_override():
                async with self.ssh.session():  # one SSH connection for the batch
                    await self.async_apply("set_allowed_days", list(ALL_DAYS))
                    await self.async_apply("set_allowed_hours", 0, 23, 0, 59)
                    await self.async_apply("set_time_limits", [UNLIMITED_DAILY] * 7)
                    await self.async_apply("set_time_limit_week", UNLIMITED_WEEKLY)
                    await self.async_apply("set_time_limit_month", UNLIMITED_MONTHLY)
                    await self.async_apply("set_time_left", "=", 86400)

            self.hass.async_create_task(_push_override())
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
        self.saved_values.pop("override_days", None)
        await self._save_state()

        # Apply all profile values to coordinator data
        for key in self._PROFILE_KEYS:
            if key in profile:
                val = profile[key]
                if isinstance(val, list):
                    val = list(val)
                data[key] = val

        # Update UI immediately, then push SSH commands in background
        self.async_set_updated_data(data)
        _LOGGER.info("Applied profile: %s", name)

        days = list(profile.get("allowed_days", data.get("allowed_days", ALL_DAYS)))

        async def _push_profile():
            async with self.ssh.session():  # one SSH connection for all 7 cmds
                await self.async_apply("set_allowed_days", days)
                await self.async_apply(
                    "set_allowed_hours",
                    profile.get("hour_start", 0),
                    profile.get("hour_end", 23),
                    profile.get("minute_start", 0),
                    profile.get("minute_end", 59),
                )
                await self.async_apply(
                    "set_time_limits",
                    self.timekpr_limits(
                        list(profile.get("daily_limits", [60] * 7)), days
                    ),
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

        self.hass.async_create_task(_push_profile())

    # ── Coordinator refresh ────────────────────────────────────────

    async def _async_update_data(self) -> dict[str, Any]:
        """Pull config and time counters from the remote machine.

        Never raises so the integration stays loaded even when the
        child's computer is turned off.
        """
        online = False
        raw_config: dict[str, str] | None = None
        time_data: dict[str, Any] = {}
        previous = self.data or self._last_known_data or {}

        # One SSH connection for the whole refresh (flush + reads).
        async with self.ssh.session() as connected:
            if connected:
                # 1. Try to flush any queued commands
                await self._flush_pending()

                # 2. Try to read current config
                try:
                    raw_config = await self.ssh.get_config(self.target_user)
                except Exception:  # noqa: BLE001
                    _LOGGER.debug("Cannot reach machine for config read")
                if not is_valid_config(raw_config):
                    raw_config = None
                online = raw_config is not None

                # 3. Time counters (best effort)
                if online:
                    time_data = await self._async_read_time(
                        process_config(raw_config, previous.get("daily_limits"))
                    )

        # 4. Build data (priority: live > previous > stored > defaults)
        if raw_config is not None:
            data = process_config(raw_config, previous.get("daily_limits"))
        elif self.data:
            # Still in memory from a previous refresh
            data = dict(self.data)
        elif self._last_known_data:
            # Restored from disk after HA restart
            data = dict(self._last_known_data)
            _LOGGER.debug("Using last known config from storage")
        else:
            data = self._default_data()

        today = dt_util.now().date()
        if online:
            # Live time values replace the previous ones; when the machine
            # answered but no counter could be read, they are unknown.
            for key in ("time_spent_today", "time_spent_week", "time_remaining"):
                data[key] = time_data.get(key)
            data["time_date"] = today.isoformat()
            # Save as last known good data
            self._last_known_data = dict(data)
            await self._save_state()
        else:
            # Offline across midnight: don't keep showing yesterday's numbers.
            roll_over_stale_time(data, today)

        data["online"] = online
        data["pending_count"] = self.pending_count

        # 5. Notification threshold from saved_values
        data["notification_threshold"] = self.saved_values.get(
            "notification_threshold", DEFAULT_NOTIFICATION_THRESHOLD
        )

        return data

    async def _async_read_time(self, config: dict[str, Any]) -> dict[str, Any]:
        """Time spent / left from Timekpr itself (issue #3).

        ``timekpra --userinfo`` gives Timekpr's own "time left today", which
        includes the manual bonus / penalty adjustments. The old computation
        (today's limit - time used) ignored them. Falls back to the control
        file (limit - *balance*) if the CLI is unavailable.
        """
        try:
            info = await self.ssh.get_user_info(self.target_user)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("timekpra --userinfo failed: %s", err)
            info = None
        values = time_values_from_userinfo(info) if info else {}
        if "time_remaining" in values:
            return values
        try:
            raw_time = await self.ssh.get_time_spent(self.target_user)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Cannot read time file: %s", err)
            raw_time = None
        if raw_time:
            fallback = time_values_from_control(
                raw_time, config, dt_util.now().date()
            )
            return {**fallback, **values}
        return values

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
