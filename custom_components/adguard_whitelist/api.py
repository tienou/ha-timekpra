"""AdGuard Home REST API client."""
from __future__ import annotations

import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=10)


class AdGuardConnectionError(Exception):
    """Cannot reach AdGuard Home."""


class AdGuardAuthError(Exception):
    """Invalid credentials."""


class AdGuardHomeAPI:
    """Async client for AdGuard Home filtering rules API."""

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
    ) -> None:
        self._base_url = url.rstrip("/")
        self._auth = aiohttp.BasicAuth(username, password)
        self._session = session

    async def get_filtering_status(self) -> dict:
        """GET /control/filtering/status."""
        try:
            async with self._session.get(
                f"{self._base_url}/control/filtering/status",
                auth=self._auth,
                timeout=_TIMEOUT,
                ssl=False,
            ) as resp:
                if resp.status == 401:
                    raise AdGuardAuthError("Invalid credentials")
                resp.raise_for_status()
                return await resp.json()
        except AdGuardAuthError:
            raise
        except aiohttp.ClientError as err:
            raise AdGuardConnectionError(str(err)) from err

    async def set_rules(self, rules: list[str]) -> None:
        """POST /control/filtering/set_rules — replaces ALL user rules."""
        try:
            async with self._session.post(
                f"{self._base_url}/control/filtering/set_rules",
                auth=self._auth,
                json={"rules": rules},
                timeout=_TIMEOUT,
                ssl=False,
            ) as resp:
                if resp.status == 401:
                    raise AdGuardAuthError("Invalid credentials")
                resp.raise_for_status()
        except AdGuardAuthError:
            raise
        except aiohttp.ClientError as err:
            raise AdGuardConnectionError(str(err)) from err

    async def test_connection(self) -> tuple[bool, str]:
        """Validate credentials by fetching filtering status.

        Returns (success, error_key) where error_key is "" on success,
        "cannot_connect" or "invalid_auth".
        """
        try:
            await self.get_filtering_status()
            return True, ""
        except AdGuardAuthError as err:
            _LOGGER.error("AdGuard auth failed: %s", err)
            return False, "invalid_auth"
        except AdGuardConnectionError as err:
            _LOGGER.error("AdGuard connection failed to %s: %s", self._base_url, err)
            return False, "cannot_connect"
        except Exception:
            _LOGGER.exception(
                "Unexpected error testing AdGuard connection to %s", self._base_url
            )
            return False, "cannot_connect"
