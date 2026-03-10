"""Config flow for AdGuard Whitelist integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
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
)

STEP_ADGUARD_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ADGUARD_URL, default="http://192.168.8.1:3000"): str,
        vol.Required(CONF_ADGUARD_USER, default="admin"): str,
        vol.Required(CONF_ADGUARD_PASSWORD): str,
        vol.Required(CONF_CLIENT_IP, default="192.168.8.50"): str,
    }
)

STEP_SSH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SSH_ENABLED, default=False): bool,
        vol.Optional(CONF_SSH_HOST): str,
        vol.Optional(CONF_SSH_PORT, default=22): int,
        vol.Optional(CONF_SSH_USER): str,
        vol.Optional(CONF_SSH_PASSWORD): str,
    }
)


class AdGuardWhitelistConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AdGuard Whitelist."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._adguard_data: dict = {}

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 1: AdGuard Home connection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = AdGuardHomeAPI(
                user_input[CONF_ADGUARD_URL],
                user_input[CONF_ADGUARD_USER],
                user_input[CONF_ADGUARD_PASSWORD],
                session,
            )
            if await api.test_connection():
                self._adguard_data = user_input
                return await self.async_step_ssh()
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_ADGUARD_SCHEMA,
            errors=errors,
        )

    async def async_step_ssh(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 2: Optional SSH for Firefox bookmarks."""
        if user_input is not None:
            data = {**self._adguard_data, **user_input}
            if not user_input.get(CONF_SSH_ENABLED):
                data.pop(CONF_SSH_HOST, None)
                data.pop(CONF_SSH_PORT, None)
                data.pop(CONF_SSH_USER, None)
                data.pop(CONF_SSH_PASSWORD, None)

            await self.async_set_unique_id(
                f"adguard_whitelist_{data[CONF_CLIENT_IP]}"
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Sites autorisés - {data[CONF_CLIENT_IP]}",
                data=data,
            )

        return self.async_show_form(
            step_id="ssh",
            data_schema=STEP_SSH_SCHEMA,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> AdGuardWhitelistOptionsFlow:
        """Get the options flow handler."""
        return AdGuardWhitelistOptionsFlow(config_entry)


class AdGuardWhitelistOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow (edit credentials after setup)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry
        self._updated: dict = {}

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 1: AdGuard Home settings."""
        if user_input is not None:
            self._updated = user_input
            return await self.async_step_ssh()

        current = self._entry.data
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ADGUARD_URL,
                    default=current.get(CONF_ADGUARD_URL, ""),
                ): str,
                vol.Required(
                    CONF_ADGUARD_USER,
                    default=current.get(CONF_ADGUARD_USER, ""),
                ): str,
                vol.Required(
                    CONF_ADGUARD_PASSWORD,
                    default=current.get(CONF_ADGUARD_PASSWORD, ""),
                ): str,
                vol.Required(
                    CONF_CLIENT_IP,
                    default=current.get(CONF_CLIENT_IP, ""),
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_ssh(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 2: SSH settings."""
        if user_input is not None:
            data = {**self._entry.data, **self._updated, **user_input}
            if not user_input.get(CONF_SSH_ENABLED):
                data.pop(CONF_SSH_HOST, None)
                data.pop(CONF_SSH_PORT, None)
                data.pop(CONF_SSH_USER, None)
                data.pop(CONF_SSH_PASSWORD, None)
            self.hass.config_entries.async_update_entry(self._entry, data=data)
            await self.hass.config_entries.async_reload(self._entry.entry_id)
            return self.async_create_entry(title="", data={})

        current = self._entry.data
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SSH_ENABLED,
                    default=current.get(CONF_SSH_ENABLED, False),
                ): bool,
                vol.Required(
                    CONF_SSH_HOST,
                    default=current.get(CONF_SSH_HOST, ""),
                ): str,
                vol.Required(
                    CONF_SSH_PORT,
                    default=current.get(CONF_SSH_PORT, 22),
                ): int,
                vol.Required(
                    CONF_SSH_USER,
                    default=current.get(CONF_SSH_USER, ""),
                ): str,
                vol.Required(
                    CONF_SSH_PASSWORD,
                    default=current.get(CONF_SSH_PASSWORD, ""),
                ): str,
            }
        )
        return self.async_show_form(step_id="ssh", data_schema=schema)
