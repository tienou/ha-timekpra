"""AdGuard Whitelist — manage allowed sites from Home Assistant."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

import voluptuous as vol

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AdGuardHomeAPI
from .const import (
    CONF_ADGUARD_PASSWORD,
    CONF_ADGUARD_URL,
    CONF_ADGUARD_USER,
    CONF_CLIENT_IP,
    CONF_SSH_ENABLED,
    CONF_SSH_HOST,
    CONF_SSH_PASSWORD,
    CONF_SSH_PORT,
    CONF_SSH_USER,
    DOMAIN,
    SERVICE_ADD_BOOKMARK,
    SERVICE_ADD_SITE,
    SERVICE_REMOVE_SITE,
)
from .coordinator import AdGuardWhitelistCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.SWITCH]

CARD_JS = "adguard-whitelist-card.js"
LOCAL_CARD_URL = f"/local/{CARD_JS}"

_CARD_REGISTERED = False


def _deploy_card(hass: HomeAssistant) -> None:
    """Copy card JS to www/ and register as extra JS resource."""
    global _CARD_REGISTERED
    if _CARD_REGISTERED:
        return

    # Copy to www/ folder (served at /local/)
    src = Path(__file__).parent / "www" / CARD_JS
    dst_dir = Path(hass.config.path("www"))
    dst_dir.mkdir(exist_ok=True)
    dst = dst_dir / CARD_JS
    try:
        shutil.copy2(str(src), str(dst))
        _LOGGER.info("AdGuard Whitelist card copied to %s", dst)
    except Exception:
        _LOGGER.warning("Could not copy card JS to %s", dst)

    # Register via add_extra_js_url — loads the JS on every HA page
    # Works reliably because manifest declares "lovelace" as dependency
    add_extra_js_url(hass, LOCAL_CARD_URL)

    _CARD_REGISTERED = True


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration domain."""
    hass.data.setdefault(DOMAIN, {})
    _deploy_card(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AdGuard Whitelist from a config entry."""
    # Ensure card is deployed even if async_setup ran before HTTP was ready
    _deploy_card(hass)
    session = async_get_clientsession(hass, verify_ssl=False)
    api = AdGuardHomeAPI(
        url=entry.data[CONF_ADGUARD_URL],
        username=entry.data[CONF_ADGUARD_USER],
        password=entry.data[CONF_ADGUARD_PASSWORD],
        session=session,
    )

    # Optional SSH client for Firefox bookmarks
    ssh_client = None
    if entry.data.get(CONF_SSH_ENABLED):
        from .ssh import FirefoxSSH

        ssh_client = FirefoxSSH(
            host=entry.data[CONF_SSH_HOST],
            port=entry.data[CONF_SSH_PORT],
            username=entry.data[CONF_SSH_USER],
            password=entry.data[CONF_SSH_PASSWORD],
        )

    coordinator = AdGuardWhitelistCoordinator(
        hass, api, entry.data[CONF_CLIENT_IP], ssh_client
    )
    await coordinator.async_load_pending()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
        "client_ip": entry.data[CONF_CLIENT_IP],
    }

    _register_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


def _register_services(hass: HomeAssistant) -> None:
    """Register add_site and remove_site services."""

    async def handle_add_site(call: ServiceCall) -> None:
        domain_name = call.data["domain"].lower().strip()
        category = call.data.get("category")
        create_bookmark = call.data.get("create_bookmark", True)
        for entry_data in hass.data[DOMAIN].values():
            if not isinstance(entry_data, dict):
                continue
            coordinator: AdGuardWhitelistCoordinator = entry_data["coordinator"]
            await coordinator.async_add_domain(
                domain_name, category=category, create_bookmark=create_bookmark
            )

    async def handle_remove_site(call: ServiceCall) -> None:
        domain_name = call.data["domain"].lower().strip()
        for entry_data in hass.data[DOMAIN].values():
            if not isinstance(entry_data, dict):
                continue
            coordinator: AdGuardWhitelistCoordinator = entry_data["coordinator"]
            await coordinator.async_remove_domain(domain_name)

    async def handle_add_bookmark(call: ServiceCall) -> None:
        domain_name = call.data["domain"].lower().strip()
        for entry_data in hass.data[DOMAIN].values():
            if not isinstance(entry_data, dict):
                continue
            coordinator: AdGuardWhitelistCoordinator = entry_data["coordinator"]
            await coordinator.async_add_bookmark(domain_name)

    if not hass.services.has_service(DOMAIN, SERVICE_ADD_SITE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_ADD_SITE,
            handle_add_site,
            schema=vol.Schema({
                vol.Required("domain"): str,
                vol.Optional("category"): str,
                vol.Optional("create_bookmark", default=True): bool,
            }),
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_REMOVE_SITE,
            handle_remove_site,
            schema=vol.Schema({vol.Required("domain"): str}),
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_ADD_BOOKMARK,
            handle_add_bookmark,
            schema=vol.Schema({vol.Required("domain"): str}),
        )
