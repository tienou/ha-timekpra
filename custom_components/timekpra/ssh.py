"""SSH connection handler for Timekpra."""
from __future__ import annotations

import logging
import re
from typing import Any

import asyncssh

_LOGGER = logging.getLogger(__name__)

CONFIG_PATHS = [
    "/etc/timekpr/timekpr.{user}.conf",
    "/etc/timekpra/timekpra.{user}.conf",
]

TIME_PATHS = [
    "/var/lib/timekpr/timekpr.{user}.time",
    "/var/lib/timekpra/timekpra.{user}.time",
]


def _sanitize(value: str) -> str:
    """Sanitize a string for safe shell use."""
    return re.sub(r"[^a-zA-Z0-9_.\-]", "", value)


class TimekpraSSH:
    """Handle SSH connections to the remote machine."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._config_path: str | None = None
        self._time_path: str | None = None

    def _sudo(self, command: str) -> str:
        """Wrap a command with sudo, using SSH password via stdin."""
        safe_pw = self._password.replace("'", "'\\''")
        return f"echo '{safe_pw}' | sudo -S {command}"

    async def execute(self, command: str) -> str:
        """Execute a command via SSH."""
        _LOGGER.debug(
            "SSH connecting to %s@%s:%s",
            self._username, self._host, self._port,
        )
        try:
            async with asyncssh.connect(
                self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                known_hosts=None,
                client_keys=[],
            ) as conn:
                result = await conn.run(command, check=False)
                rc = getattr(result, "returncode", None) or getattr(result, "exit_status", None)
                if rc and rc != 0:
                    _LOGGER.warning(
                        "Command exited with %s: %s | stderr: %s",
                        rc, command, result.stderr,
                    )
                return result.stdout or ""
        except asyncssh.PermissionDenied as err:
            _LOGGER.error("SSH auth failed (wrong password?): %s", err)
            raise
        except asyncssh.DisconnectError as err:
            _LOGGER.error("SSH disconnect: code=%s reason=%s", err.code, err.reason)
            raise
        except OSError as err:
            _LOGGER.error("SSH network error (host unreachable?): %s", err)
            raise
        except Exception as err:
            _LOGGER.error("SSH unexpected error [%s]: %s", type(err).__name__, err)
            raise

    async def test_connection(self) -> bool:
        """Test SSH connectivity."""
        try:
            result = await self.execute("echo ok")
            return "ok" in result
        except Exception as err:
            _LOGGER.error("SSH connection test failed: %s", err)
            return False

    # ── Config reading ─────────────────────────────────────────────

    async def _find_path(self, user: str, candidates: list[str]) -> str | None:
        """Find an existing file among candidates."""
        for template in candidates:
            path = template.format(user=_sanitize(user))
            result = await self.execute(self._sudo(f"test -f {path}") + " && echo found")
            if "found" in result:
                return path
        return None

    async def get_config(self, user: str) -> dict[str, str] | None:
        """Read and parse timekpra config for a user."""
        if not self._config_path:
            self._config_path = await self._find_path(user, CONFIG_PATHS)
        if not self._config_path:
            _LOGGER.error("Config file not found for user %s", user)
            return None
        try:
            output = await self.execute(self._sudo(f"cat {self._config_path}"))
            return self._parse_ini(output)
        except Exception as err:
            _LOGGER.error("Failed to read config: %s", err)
            return None

    async def get_time_spent(self, user: str) -> dict[str, str] | None:
        """Read time-tracking data for a user."""
        if not self._time_path:
            self._time_path = await self._find_path(user, TIME_PATHS)
        if not self._time_path:
            return None
        try:
            output = await self.execute(self._sudo(f"cat {self._time_path}"))
            return self._parse_ini(output)
        except Exception:
            return None

    @staticmethod
    def _parse_ini(raw: str) -> dict[str, str]:
        """Parse an INI-style file into a flat dict (ignoring sections)."""
        config: dict[str, str] = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("["):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                config[key.strip()] = value.strip()
        return config

    # ── Setters (timekpra CLI) ─────────────────────────────────────

    async def set_allowed_days(self, user: str, days: list[int]) -> None:
        """Set which week days the user is allowed to log in."""
        safe_user = _sanitize(user)
        days_str = ";".join(str(d) for d in sorted(days))
        await self.execute(
            self._sudo(f"timekpra --setalloweddays '{safe_user}' '{days_str}'")
        )

    async def set_allowed_hours(
        self, user: str, hour_start: int, hour_end: int
    ) -> None:
        """Set allowed login hours (same for all days)."""
        safe_user = _sanitize(user)
        hours = ";".join(str(h) for h in range(hour_start, hour_end + 1))
        await self.execute(
            self._sudo(f"timekpra --setallowedhours '{safe_user}' 'ALL' '{hours}'")
        )

    async def set_time_limits(self, user: str, limits_minutes: list[int]) -> None:
        """Set per-day time limits (list of 7 values in minutes)."""
        safe_user = _sanitize(user)
        parts: list[str] = []
        for m in limits_minutes:
            if m >= 60 and m % 60 == 0:
                parts.append(f"{m // 60}h")
            else:
                parts.append(f"{m}m")
        limits_str = ";".join(parts)
        await self.execute(
            self._sudo(f"timekpra --settimelimits '{safe_user}' '{limits_str}'")
        )

    async def set_time_limit_week(self, user: str, hours: int) -> None:
        safe_user = _sanitize(user)
        await self.execute(
            self._sudo(f"timekpra --settimelimitweek '{safe_user}' '{hours}h'")
        )

    async def set_time_limit_month(self, user: str, hours: int) -> None:
        safe_user = _sanitize(user)
        await self.execute(
            self._sudo(f"timekpra --settimelimitmonth '{safe_user}' '{hours}h'")
        )

    async def set_track_inactive(self, user: str, track: bool) -> None:
        safe_user = _sanitize(user)
        val = "true" if track else "false"
        await self.execute(
            self._sudo(f"timekpra --settrackinactive '{safe_user}' '{val}'")
        )

    async def set_lockout_type(self, user: str, lockout_type: str) -> None:
        safe_user = _sanitize(user)
        safe_type = _sanitize(lockout_type)
        await self.execute(
            self._sudo(f"timekpra --setlockouttype '{safe_user}' '{safe_type}'")
        )
