"""SSH client for managing Firefox policies.json on a remote machine."""
from __future__ import annotations

import logging

import asyncssh

from .const import FIREFOX_POLICIES_PATH
from .firefox import (
    add_bookmark,
    parse_policies,
    remove_bookmark,
    serialize_policies,
)

_LOGGER = logging.getLogger(__name__)


class FirefoxSSH:
    """Handle SSH connections to sync Firefox bookmarks."""

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

    def _sudo(self, command: str) -> str:
        safe_pw = self._password.replace("'", "'\\''")
        return f"echo '{safe_pw}' | sudo -S {command}"

    async def execute(self, command: str) -> str:
        """Execute a command via SSH using create_process for reliable output."""
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
                proc = await conn.create_process(command)
                stdout_data = await proc.stdout.read()
                await proc.wait_closed()
                return stdout_data or ""
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

    async def _read_policies(self) -> dict:
        """Read and parse the current policies.json."""
        raw = await self.execute(
            self._sudo(f"cat {FIREFOX_POLICIES_PATH}")
        )
        return parse_policies(raw)

    async def _write_policies(self, policies: dict) -> None:
        """Write policies.json back to the remote machine."""
        content = serialize_policies(policies)
        # Escape for shell: use heredoc via stdin
        safe_content = content.replace("'", "'\\''")
        cmd = (
            self._sudo(f"tee {FIREFOX_POLICIES_PATH}") +
            f" <<'ENDPOLICIES'\n{content}ENDPOLICIES"
        )
        await self.execute(cmd)

    async def add_bookmark(self, domain: str) -> None:
        """Add a bookmark to Firefox policies.json."""
        policies = await self._read_policies()
        new_policies = add_bookmark(policies, domain)
        await self._write_policies(new_policies)
        _LOGGER.info("Firefox bookmark added: %s", domain)

    async def remove_bookmark(self, domain: str) -> None:
        """Remove a bookmark from Firefox policies.json."""
        policies = await self._read_policies()
        new_policies = remove_bookmark(policies, domain)
        await self._write_policies(new_policies)
        _LOGGER.info("Firefox bookmark removed: %s", domain)
