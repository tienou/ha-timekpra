"""Data update coordinator for AdGuard Whitelist with offline SSH queue."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import asyncssh

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import AdGuardConnectionError, AdGuardHomeAPI
from .const import DOMAIN, SCAN_INTERVAL_SECONDS
from .rules import categorize_all, categorize_domain, parse_whitelist_rules

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


class AdGuardWhitelistCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch AdGuard rules and manage the SSH offline queue."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: AdGuardHomeAPI,
        client_ip: str,
        ssh_client: Any | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self.api = api
        self.client_ip = client_ip
        self.ssh_client = ssh_client
        # Key on client_ip so pending commands survive entry reinstalls
        safe_ip = client_ip.replace(".", "_")
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_pending_{safe_ip}")
        self._meta_store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_meta_{safe_ip}")
        self._pending_ssh: list[dict[str, str]] = []
        # domain → {"category": str, "has_bookmark": bool}
        self._domain_meta: dict[str, dict[str, Any]] = {}

    # ── Persistent SSH queue ────────────────────────────────────

    async def async_load_pending(self) -> None:
        """Load queued SSH commands and domain metadata from disk."""
        data = await self._store.async_load()
        if isinstance(data, dict):
            self._pending_ssh = data.get("pending_ssh", [])
            if self._pending_ssh:
                _LOGGER.info(
                    "Loaded %d pending SSH command(s)", len(self._pending_ssh)
                )

        meta = await self._meta_store.async_load()
        if isinstance(meta, dict):
            self._domain_meta = meta
            _LOGGER.debug("Loaded metadata for %d domain(s)", len(self._domain_meta))

    async def _save_pending(self) -> None:
        await self._store.async_save({"pending_ssh": list(self._pending_ssh)})

    async def _save_meta(self) -> None:
        await self._meta_store.async_save(dict(self._domain_meta))

    async def _flush_ssh_pending(self) -> None:
        """Replay queued SSH commands if the machine is online."""
        if not self._pending_ssh or not self.ssh_client:
            return

        flushed: list[int] = []
        for i, cmd in enumerate(self._pending_ssh):
            try:
                action = cmd["action"]
                domain = cmd["domain"]
                if action == "add":
                    await self.ssh_client.add_bookmark(domain)
                elif action == "remove":
                    await self.ssh_client.remove_bookmark(domain)
                flushed.append(i)
                _LOGGER.info("Flushed pending SSH: %s %s", action, domain)
            except (OSError, asyncssh.Error) as err:
                _LOGGER.debug("SSH still offline: %s", err)
                break
            except Exception as err:
                _LOGGER.warning("SSH unexpected error during flush: %s", err)
                break

        if flushed:
            for i in reversed(flushed):
                self._pending_ssh.pop(i)
            await self._save_pending()

    async def _queue_ssh(self, action: str, domain: str) -> None:
        """Queue an SSH command, executing immediately if possible."""
        if not self.ssh_client:
            return

        try:
            if action == "add":
                await self.ssh_client.add_bookmark(domain)
            elif action == "remove":
                await self.ssh_client.remove_bookmark(domain)
        except (OSError, asyncssh.Error):
            _LOGGER.info("PC offline — queuing SSH %s %s", action, domain)
            self._pending_ssh.append({"action": action, "domain": domain})
            await self._save_pending()
        except Exception as err:
            _LOGGER.warning("SSH unexpected error — queuing %s %s: %s", action, domain, err)
            self._pending_ssh.append({"action": action, "domain": domain})
            await self._save_pending()

    @property
    def pending_count(self) -> int:
        return len(self._pending_ssh)

    @property
    def ssh_enabled(self) -> bool:
        return self.ssh_client is not None

    # ── Domain metadata ──────────────────────────────────────────

    def get_domain_meta(self, domain: str) -> dict[str, Any]:
        """Get metadata for a domain."""
        return self._domain_meta.get(domain, {})

    def get_bookmarked_domains(self) -> set[str]:
        """Return set of domains that have Firefox bookmarks."""
        return {
            d for d, m in self._domain_meta.items() if m.get("has_bookmark")
        }

    async def _sync_bookmarks_from_firefox(self) -> None:
        """Sync bookmark metadata by reading actual Firefox bookmarks via SSH."""
        if not self.ssh_client:
            return

        try:
            real_bookmarks = await self.ssh_client.get_existing_bookmarks()
            _LOGGER.debug(
                "Synced %d Firefox bookmarks from remote", len(real_bookmarks)
            )
            changed = False
            for domain in real_bookmarks:
                meta = self._domain_meta.get(domain, {})
                if not meta.get("has_bookmark"):
                    meta["has_bookmark"] = True
                    self._domain_meta[domain] = meta
                    changed = True
            # Also clear has_bookmark for domains no longer bookmarked
            for domain, meta in list(self._domain_meta.items()):
                if meta.get("has_bookmark") and domain not in real_bookmarks:
                    meta["has_bookmark"] = False
                    changed = True
            if changed:
                await self._save_meta()
        except (OSError, asyncssh.Error) as err:
            _LOGGER.debug("Cannot sync Firefox bookmarks (PC offline?): %s", err)
        except Exception as err:
            _LOGGER.warning("Error syncing Firefox bookmarks: %s", err)

    # ── AdGuard operations ──────────────────────────────────────

    async def async_add_domain(
        self,
        domain: str,
        category: str | None = None,
        create_bookmark: bool = True,
    ) -> None:
        """Add a whitelisted domain to AdGuard and optionally Firefox."""
        from .rules import add_domain_to_rules

        status = await self.api.get_filtering_status()
        current_rules = status.get("user_rules", [])
        new_rules = add_domain_to_rules(current_rules, domain, self.client_ip)
        await self.api.set_rules(new_rules)

        # Store metadata
        meta: dict[str, Any] = {}
        if category:
            meta["category"] = category
        if create_bookmark and self.ssh_client:
            await self._queue_ssh("add", domain)
            meta["has_bookmark"] = True
        else:
            meta["has_bookmark"] = False

        self._domain_meta[domain] = meta
        await self._save_meta()
        await self.async_request_refresh()

    async def async_add_bookmark(self, domain: str) -> None:
        """Add a Firefox bookmark for an already whitelisted domain."""
        if not self.ssh_client:
            return
        await self._queue_ssh("add", domain)
        meta = self._domain_meta.get(domain, {})
        meta["has_bookmark"] = True
        self._domain_meta[domain] = meta
        await self._save_meta()
        await self.async_request_refresh()

    async def async_remove_domain(self, domain: str) -> None:
        """Remove a whitelisted domain from AdGuard and optionally Firefox."""
        from .rules import remove_domain_from_rules

        status = await self.api.get_filtering_status()
        current_rules = status.get("user_rules", [])
        new_rules = remove_domain_from_rules(current_rules, domain, self.client_ip)
        await self.api.set_rules(new_rules)

        # Remove bookmark if it existed
        if self._domain_meta.get(domain, {}).get("has_bookmark"):
            await self._queue_ssh("remove", domain)

        self._domain_meta.pop(domain, None)
        await self._save_meta()
        await self.async_request_refresh()

    # ── Coordinator refresh ─────────────────────────────────────

    async def _async_update_data(self) -> dict[str, Any]:
        """Pull current rules from AdGuard Home."""
        # Flush SSH queue first
        await self._flush_ssh_pending()

        # Sync bookmark metadata from Firefox
        await self._sync_bookmarks_from_firefox()

        # Check SSH reachability (already attempted during flush/sync above)
        ssh_reachable = False
        if self.ssh_client:
            try:
                await self.ssh_client.execute("echo ok")
                ssh_reachable = True
            except Exception:
                ssh_reachable = False

        adguard_reachable = True
        try:
            status = await self.api.get_filtering_status()
        except AdGuardConnectionError as err:
            _LOGGER.warning("Cannot reach AdGuard Home: %s", err)
            adguard_reachable = False
            if self.data:
                prev = dict(self.data)
                prev["adguard_reachable"] = False
                prev["ssh_reachable"] = ssh_reachable
                return prev
            return {
                "domains": [],
                "count": 0,
                "categories": {},
                "all_rules_count": 0,
                "pending_ssh": self.pending_count,
                "bookmarked_domains": [],
                "ssh_enabled": self.ssh_enabled,
                "adguard_reachable": False,
                "ssh_reachable": ssh_reachable,
            }

        all_rules = status.get("user_rules", [])
        domains = parse_whitelist_rules(all_rules, self.client_ip)

        # Use user-assigned categories, fallback to auto-detect
        categories: dict[str, list[str]] = {}
        for d in domains:
            meta = self._domain_meta.get(d, {})
            cat = meta.get("category") or categorize_domain(d)
            categories.setdefault(cat, []).append(d)

        bookmarked = sorted(self.get_bookmarked_domains())

        return {
            "domains": domains,
            "count": len(domains),
            "categories": categories,
            "all_rules_count": len(all_rules),
            "pending_ssh": self.pending_count,
            "bookmarked_domains": bookmarked,
            "ssh_enabled": self.ssh_enabled,
            "adguard_reachable": adguard_reachable,
            "ssh_reachable": ssh_reachable,
        }
