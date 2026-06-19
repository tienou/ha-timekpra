"""Config flow for the Timekpra integration."""
from __future__ import annotations

from typing import Any

import asyncssh
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    AUTH_KEY,
    AUTH_PASSWORD,
    CONF_AUTH_METHOD,
    CONF_SSH_HOST,
    CONF_SSH_HOST_VPN,
    CONF_SSH_KEY,
    CONF_SSH_KEY_PASSPHRASE,
    CONF_SSH_PASSWORD,
    CONF_SSH_PORT,
    CONF_SSH_USER,
    CONF_SUDO_PASSWORD,
    CONF_TARGET_USER,
    DOMAIN,
)


def _build_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the connection schema, pre-filled with ``defaults``."""
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_SSH_HOST, default=d.get(CONF_SSH_HOST, "")): str,
            vol.Optional(
                CONF_SSH_HOST_VPN, default=d.get(CONF_SSH_HOST_VPN, "")
            ): str,
            vol.Required(CONF_SSH_PORT, default=d.get(CONF_SSH_PORT, 22)): int,
            vol.Required(CONF_SSH_USER, default=d.get(CONF_SSH_USER, "")): str,
            vol.Required(
                CONF_AUTH_METHOD, default=d.get(CONF_AUTH_METHOD, AUTH_PASSWORD)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value=AUTH_PASSWORD, label="Mot de passe"
                        ),
                        selector.SelectOptionDict(value=AUTH_KEY, label="Clé SSH"),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_SSH_PASSWORD, default=d.get(CONF_SSH_PASSWORD, "")
            ): str,
            vol.Optional(
                CONF_SSH_KEY, default=d.get(CONF_SSH_KEY, "")
            ): selector.TextSelector(
                selector.TextSelectorConfig(multiline=True)
            ),
            vol.Optional(
                CONF_SSH_KEY_PASSPHRASE, default=d.get(CONF_SSH_KEY_PASSPHRASE, "")
            ): str,
            vol.Optional(
                CONF_SUDO_PASSWORD, default=d.get(CONF_SUDO_PASSWORD, "")
            ): str,
            vol.Required(
                CONF_TARGET_USER, default=d.get(CONF_TARGET_USER, "camille")
            ): str,
        }
    )


def _validate(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate the auth fields locally (no network — stays offline-friendly).

    Returns a mapping of field -> error key (empty when everything is valid).
    """
    errors: dict[str, str] = {}
    method = user_input.get(CONF_AUTH_METHOD, AUTH_PASSWORD)

    if method == AUTH_PASSWORD:
        if not user_input.get(CONF_SSH_PASSWORD):
            errors[CONF_SSH_PASSWORD] = "password_required"
    else:  # AUTH_KEY
        key = user_input.get(CONF_SSH_KEY, "")
        if not key:
            errors[CONF_SSH_KEY] = "key_required"
        else:
            try:
                asyncssh.import_private_key(
                    key,
                    passphrase=user_input.get(CONF_SSH_KEY_PASSPHRASE) or None,
                )
            except asyncssh.KeyImportError:
                errors[CONF_SSH_KEY] = "invalid_key"
            except Exception:  # malformed input, wrong passphrase, etc.
                errors[CONF_SSH_KEY] = "invalid_key"

    return errors


def _normalize(user_input: dict[str, Any]) -> dict[str, Any]:
    """Drop credentials that don't apply to the chosen auth method."""
    data = dict(user_input)
    method = data.get(CONF_AUTH_METHOD, AUTH_PASSWORD)
    if method == AUTH_PASSWORD:
        data.pop(CONF_SSH_KEY, None)
        data.pop(CONF_SSH_KEY_PASSPHRASE, None)
    else:  # AUTH_KEY — SSH password is irrelevant (sudo uses sudo_password)
        data.pop(CONF_SSH_PASSWORD, None)
    return data


class TimekpraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Timekpra."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial configuration step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                await self.async_set_unique_id(
                    f"timekpra_{user_input[CONF_SSH_HOST]}_{user_input[CONF_TARGET_USER]}"
                )
                self._abort_if_unique_id_configured()
                data = _normalize(user_input)
                return self.async_create_entry(
                    title=f"Timekpra - {data[CONF_TARGET_USER]}",
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> TimekpraOptionsFlow:
        """Get the options flow handler."""
        return TimekpraOptionsFlow()


class TimekpraOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Timekpra (edit credentials / auth method)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show the options form pre-filled with current values."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                data = _normalize({**self.config_entry.data, **user_input})
                self.hass.config_entries.async_update_entry(self.config_entry, data=data)
                return self.async_create_entry(title="", data={})
            defaults = user_input
        else:
            defaults = dict(self.config_entry.data)

        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(defaults),
            errors=errors,
        )
