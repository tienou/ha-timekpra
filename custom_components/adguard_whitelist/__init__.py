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
    SERVICE_ADD_SITE,
    SERVICE_REMOVE_SITE,
)
from .coordinator import AdGuardWhitelistCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.SWITCH]

CARD_JS = "adguard-whitelist-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_JS}"
LOCAL_CARD_URL = f"/local/{CARD_JS}"

_CARD_REGISTERED = False


def _deploy_card(hass: HomeAssistant) -> None:
    """Copy card JS to www/ and register as Lovelace resource."""
    global _CARD_REGISTERED
    if _CARD_REGISTERED:
        return

    # 1. Copy to www/ folder (served at /local/)
    src = Path(__file__).parent / "www" / CARD_JS
    dst_dir = Path(hass.config.path("www"))
    dst_dir.mkdir(exist_ok=True)
    dst = dst_dir / CARD_JS
    try:
        shutil.copy2(str(src), str(dst))
        _LOGGER.info("AdGuard Whitelist card copied to %s", dst)
    except Exception:
        _LOGGER.warning("Could not copy card JS to %s", dst)

    # 2. Register via add_extra_js_url so HA auto-loads it on every page
    add_extra_js_url(hass, LOCAL_CARD_URL)

    # 3. Also register a static path so /adguard_whitelist/card.js works too
    try:
        hass.http.register_static_path(
            CARD_URL, str(src), cache_headers=False
        )
    except Exception:
        pass

    # 4. Register as a Lovelace resource in the resource store
    hass.async_create_task(_async_register_lovelace_resource(hass))

    _CARD_REGISTERED = True


async def _async_register_lovelace_resource(hass: HomeAssistant) -> None:
    """Ensure the card JS is in the Lovelace resource list."""
    try:
        # Wait for lovelace resources to be available
        from homeassistant.components.lovelace import DOMAIN as LOVELACE_DOMAIN
        from homeassistant.components.lovelace.resources import (
            ResourceStorageCollection,
        )

        # Get the lovelace resources collection
        lovelace_data = hass.data.get(LOVELACE_DOMAIN)
        if lovelace_data is None:
            return

        resources = lovelace_data.get("resources")
        if resources is None or not isinstance(resources, ResourceStorageCollection):
            return

        # Check if already registered
        for item in resources.async_items():
            if LOCAL_CARD_URL in item.get("url", ""):
                _LOGGER.debug("Lovelace resource already registered")
                return

        # Add as JS resource
        await resources.async_create_item(
            {"res_type": "js", "url": LOCAL_CARD_URL}
        )
        _LOGGER.info("Lovelace resource registered: %s", LOCAL_CARD_URL)
    except Exception as err:
        _LOGGER.debug(
            "Could not auto-register Lovelace resource (manual add may be needed): %s",
            err,
        )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration domain."""
    hass.data.setdefault(DOMAIN, {})
    _deploy_card(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AdGuard Whitelist from a config entry."""
    # Ensure card is deployed even if async_setup ran before HTTP was ready
    _deploy_card(hass)
    session = async_get_clientsession(hass)
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
        for entry_data in hass.data[DOMAIN].values():
            if not isinstance(entry_data, dict):
                continue
            coordinator: AdGuardWhitelistCoordinator = entry_data["coordinator"]
            await coordinator.async_add_domain(domain_name)

    async def handle_remove_site(call: ServiceCall) -> None:
        domain_name = call.data["domain"].lower().strip()
        for entry_data in hass.data[DOMAIN].values():
            if not isinstance(entry_data, dict):
                continue
            coordinator: AdGuardWhitelistCoordinator = entry_data["coordinator"]
            await coordinator.async_remove_domain(domain_name)

    if not hass.services.has_service(DOMAIN, SERVICE_ADD_SITE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_ADD_SITE,
            handle_add_site,
            schema=vol.Schema({vol.Required("domain"): str}),
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_REMOVE_SITE,
            handle_remove_site,
            schema=vol.Schema({vol.Required("domain"): str}),
        )
