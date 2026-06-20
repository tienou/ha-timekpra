"""SSH connection handler for Timekpra."""
from __future__ import annotations

import logging
import re
from typing import Any

import asyncssh

_LOGGER = logging.getLogger(__name__)

CONFIG_PATHS = [
    "/var/lib/timekpr/config/timekpr.{user}.conf",
    "/etc/timekpr/timekpra.{user}.conf",
    "/etc/timekpr/timekpr.{user}.conf",
    "/etc/timekpra/timekpra.{user}.conf",
]

TIME_PATHS = [
    "/var/lib/timekpr/work/{user}.time",
    "/var/lib/timekpr/work/timekpra.{user}.time",
    "/var/lib/timekpra/timekpra.{user}.time",
]


def _sanitize(value: str) -> str:
    """Sanitize a string for safe shell use."""
    return re.sub(r"[^a-zA-Z0-9_.\-]", "", value)


class TimekpraCommandError(Exception):
    """A remote command was reached but exited non-zero.

    Distinct from connectivity errors (``OSError`` / ``asyncssh.Error``):
    the machine answered, but the command itself failed (e.g. wrong sudo
    password, missing NOPASSWD rule, or a ``timekpra`` CLI error). Such a
    failure must NOT be mistaken for success or for "machine offline".
    """


class TimekpraSSH:
    """Handle SSH connections to the remote machine."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str = "",
        host_vpn: str = "",
        ssh_key: str = "",
        ssh_key_passphrase: str = "",
        sudo_password: str = "",
        host_key: str = "",
    ) -> None:
        self._host = host
        self._host_vpn = host_vpn
        self._port = port
        self._username = username
        self._password = password
        self._ssh_key = ssh_key
        self._ssh_key_passphrase = ssh_key_passphrase
        # Password used for ``sudo -S``. Falls back to the SSH password so
        # existing password-based setups keep working unchanged. When empty
        # (typical with key auth) we rely on passwordless sudo (NOPASSWD).
        self._sudo_password = sudo_password or password
        self._client_keys: list | None = None
        # Pinned server host key (OpenSSH public-key line). Empty until the
        # first connection learns it (Trust On First Use). When set, the
        # server must present this exact key or the connection is refused.
        self._host_key = host_key
        # Async callback invoked with the learned key so the caller can
        # persist it. Set by the coordinator after loading its store.
        self.host_key_saver: Any = None
        self._config_path: str | None = None
        self._time_path: str | None = None

    def set_host_key(self, host_key: str) -> None:
        """Set (or clear) the pinned host key."""
        self._host_key = host_key or ""

    def _known_hosts(self) -> Any:
        """Build the asyncssh ``known_hosts`` argument.

        Returns a single-key trust tuple when a key is pinned (asyncssh
        then rejects any other host key), or ``None`` to accept the key on
        first use (TOFU). A stored-but-unparseable key is discarded so the
        next connection re-learns it rather than failing forever.
        """
        if self._host_key:
            try:
                return ([asyncssh.import_public_key(self._host_key)], [], [])
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "Stored host key unreadable (%s); will re-learn on next connect",
                    err,
                )
                self._host_key = ""
        return None

    async def _learn_host_key(self, conn: asyncssh.SSHClientConnection) -> None:
        """Capture and persist the server host key on first connect (TOFU)."""
        try:
            server_key = conn.get_server_host_key()
            if server_key is None:
                return
            key_str = server_key.export_public_key().decode().strip()
            self._host_key = key_str
            _LOGGER.info(
                "Pinned SSH host key (%s)", server_key.get_fingerprint()
            )
            if self.host_key_saver is not None:
                await self.host_key_saver(key_str)
        except Exception as err:  # noqa: BLE001 — never break a working connection
            _LOGGER.debug("Could not capture host key for pinning: %s", err)

    def _get_client_keys(self) -> list:
        """Parse the private key once and cache it.

        Raises ``asyncssh.KeyImportError`` if the key (or its passphrase)
        is invalid.
        """
        if not self._ssh_key:
            return []
        if self._client_keys is None:
            key = asyncssh.import_private_key(
                self._ssh_key,
                passphrase=self._ssh_key_passphrase or None,
            )
            self._client_keys = [key]
        return self._client_keys

    def _sudo(self, command: str) -> str:
        """Wrap a command with sudo.

        Uses the sudo password via stdin when one is available, otherwise
        falls back to non-interactive sudo (requires NOPASSWD on the host).
        ``-p ''`` suppresses the prompt so it never leaks into stdout.
        """
        if self._sudo_password:
            safe_pw = self._sudo_password.replace("'", "'\\''")
            return f"echo '{safe_pw}' | sudo -S -p '' {command}"
        return f"sudo -n {command}"

    async def _execute_on_host(
        self, host: str, command: str, check: bool = False
    ) -> str:
        """Execute a command via SSH on a specific host."""
        _LOGGER.debug(
            "SSH connecting to %s@%s:%s (%s auth)",
            self._username, host, self._port,
            "key" if self._ssh_key else "password",
        )
        connect_kwargs: dict[str, Any] = {
            "port": self._port,
            "username": self._username,
            # Pinned key once known; None accepts the key on first use (TOFU).
            "known_hosts": self._known_hosts(),
            "login_timeout": 10,
        }
        if self._ssh_key:
            # Key-based auth: never send the password to the SSH layer.
            connect_kwargs["client_keys"] = self._get_client_keys()
        else:
            connect_kwargs["password"] = self._password
            connect_kwargs["client_keys"] = []

        async with asyncssh.connect(host, **connect_kwargs) as conn:
            if not self._host_key:
                await self._learn_host_key(conn)
            result = await conn.run(command, check=False)
            if check and result.exit_status != 0:
                stderr = (result.stderr or "").strip()
                raise TimekpraCommandError(
                    f"exit {result.exit_status}: {stderr or 'no error output'}"
                )
            return result.stdout or ""

    async def execute(self, command: str, check: bool = False) -> str:
        """Execute a command via SSH, trying the VPN host as fallback.

        When ``check`` is True, a non-zero exit status raises
        ``TimekpraCommandError`` instead of silently returning empty output.
        """
        hosts = [self._host]
        if self._host_vpn:
            hosts.append(self._host_vpn)

        last_err: Exception | None = None
        for host in hosts:
            try:
                return await self._execute_on_host(host, command, check)
            except TimekpraCommandError:
                # The machine answered and the command failed; the VPN host
                # is the same machine, so don't retry — surface it.
                raise
            except asyncssh.PermissionDenied as err:
                _LOGGER.error("SSH auth failed on %s: %s", host, err)
                raise
            except asyncssh.HostKeyNotVerifiable as err:
                # Fail closed: do NOT send credentials to an unverified host.
                _LOGGER.error(
                    "SSH host key mismatch on %s — refusing to connect "
                    "(possible MITM, or the machine's host key changed). "
                    "Re-add the integration to re-pin the key. %s",
                    host, err,
                )
                last_err = err
            except asyncssh.DisconnectError as err:
                _LOGGER.debug("SSH disconnect on %s: code=%s reason=%s", host, err.code, err.reason)
                last_err = err
            except OSError as err:
                _LOGGER.debug("SSH unreachable on %s: %s", host, err)
                last_err = err
            except Exception as err:
                _LOGGER.debug("SSH error on %s [%s]: %s", host, type(err).__name__, err)
                last_err = err

        _LOGGER.error("SSH failed on all hosts (%s): %s", ", ".join(hosts), last_err)
        raise last_err  # type: ignore[misc]

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
        """Find an existing file among candidates, with filesystem search fallback."""
        safe_user = _sanitize(user)
        # Try known paths first
        for template in candidates:
            path = template.format(user=safe_user)
            result = await self.execute(self._sudo(f"test -f {path}") + " && echo found")
            if "found" in result:
                _LOGGER.debug("Found config at known path: %s", path)
                return path
        # Fallback: search the filesystem
        _LOGGER.debug("Known paths failed, searching filesystem for *%s*.conf", safe_user)
        result = await self.execute(
            self._sudo(f"find /etc /var/lib -name '*{safe_user}*.conf' -o -name '*{safe_user}*.time' 2>/dev/null")
        )
        if result.strip():
            _LOGGER.info("Filesystem search found: %s", result.strip())
        else:
            _LOGGER.warning("No config/time files found for user %s on filesystem", safe_user)
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
            self._sudo(f"timekpra --setalloweddays '{safe_user}' '{days_str}'"),
            check=True,
        )

    async def set_allowed_hours(
        self,
        user: str,
        hour_start: int,
        hour_end: int,
        minute_start: int = 0,
        minute_end: int = 59,
    ) -> None:
        """Set allowed login hours with optional minute precision.

        Uses timekpra bracket syntax: ``hour[mm_start-mm_end]``.
        Example: ``7[30-59];8;9;...;20[00-45]`` for 7:30→20:45.
        """
        safe_user = _sanitize(user)

        # When minute_end is 0, the user means "up to hour_end:00",
        # i.e. the last full allowed hour is hour_end - 1.
        if minute_end == 0 and hour_end > hour_start:
            hour_end -= 1
            minute_end = 59

        parts: list[str] = []
        for h in range(hour_start, hour_end + 1):
            if h == hour_start == hour_end:
                # Single-hour range
                if minute_start > 0 or minute_end < 59:
                    parts.append(f"{h}[{minute_start:02d}-{minute_end:02d}]")
                else:
                    parts.append(str(h))
            elif h == hour_start and minute_start > 0:
                parts.append(f"{h}[{minute_start:02d}-59]")
            elif h == hour_end and minute_end < 59:
                parts.append(f"{h}[00-{minute_end:02d}]")
            else:
                parts.append(str(h))

        hours_str = ";".join(parts)
        await self.execute(
            self._sudo(f"timekpra --setallowedhours '{safe_user}' 'ALL' '{hours_str}'"),
            check=True,
        )

    async def set_time_limits(self, user: str, limits_minutes: list[int]) -> None:
        """Set per-day time limits (7 values given in minutes).

        timekpr expects integer SECONDS per weekday, so convert minutes → s.
        (Read side parses LIMITS_PER_WEEKDAYS as seconds // 60.)
        """
        safe_user = _sanitize(user)
        limits_str = ";".join(str(int(m) * 60) for m in limits_minutes)
        await self.execute(
            self._sudo(f"timekpra --settimelimits '{safe_user}' '{limits_str}'"),
            check=True,
        )

    async def set_time_limit_week(self, user: str, hours: int) -> None:
        """Set the weekly limit (given in hours). timekpr expects SECONDS."""
        safe_user = _sanitize(user)
        await self.execute(
            self._sudo(
                f"timekpra --settimelimitweek '{safe_user}' '{int(hours) * 3600}'"
            ),
            check=True,
        )

    async def set_time_limit_month(self, user: str, hours: int) -> None:
        """Set the monthly limit (given in hours). timekpr expects SECONDS."""
        safe_user = _sanitize(user)
        await self.execute(
            self._sudo(
                f"timekpra --settimelimitmonth '{safe_user}' '{int(hours) * 3600}'"
            ),
            check=True,
        )

    async def set_track_inactive(self, user: str, track: bool) -> None:
        safe_user = _sanitize(user)
        val = "true" if track else "false"
        await self.execute(
            self._sudo(f"timekpra --settrackinactive '{safe_user}' '{val}'"),
            check=True,
        )

    async def set_time_left(self, user: str, operator: str, seconds: int) -> None:
        """Set time left for user: operator is '+', '-', or '='."""
        safe_user = _sanitize(user)
        await self.execute(
            self._sudo(f"timekpra --settimeleft '{safe_user}' '{operator}' '{seconds}'"),
            check=True,
        )

    async def set_lockout_type(self, user: str, lockout_type: str) -> None:
        safe_user = _sanitize(user)
        safe_type = _sanitize(lockout_type)
        await self.execute(
            self._sudo(f"timekpra --setlockouttype '{safe_user}' '{safe_type}'"),
            check=True,
        )
