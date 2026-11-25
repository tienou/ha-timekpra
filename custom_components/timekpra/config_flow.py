"""Config flow for the Timekpra integration."""
from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

import asyncssh
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
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

# Secrets are never sent back to the browser as field defaults; in the
# options / re-auth forms an empty secret field means "keep the current one".
SECRET_FIELDS = (CONF_SSH_PASSWORD, CONF_SSH_KEY, CONF_SSH_KEY_PASSPHRASE, CONF_SUDO_PASSWORD)

_PASSWORD = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)
_KEY = selector.TextSelector(selector.TextSelectorConfig(multiline=True))


def _build_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the connection schema, pre-filled with ``defaults`` (no secrets)."""
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_SSH_HOST, default=d.get(CONF_SSH_HOST, "")): str,
            vol.Optional(
                CONF_SSH_HOST_VPN, default=d.get(CONF_SSH_HOST_VPN, "")
            ): str,
            vol.Required(CONF_SSH_PORT, default=d.get(CONF_SSH_PORT, 22)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
            vol.Required(CONF_SSH_USER, default=d.get(CONF_SSH_USER, "")): str,
            vol.Required(
                CONF_AUTH_METHOD, default=d.get(CONF_AUTH_METHOD, AUTH_PASSWORD)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[AUTH_PASSWORD, AUTH_KEY],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    # Labels come from translations (selector.auth_method).
                    translation_key=CONF_AUTH_METHOD,
                )
            ),
            vol.Optional(CONF_SSH_PASSWORD): _PASSWORD,
            vol.Optional(CONF_SSH_KEY): _KEY,
            vol.Optional(CONF_SSH_KEY_PASSPHRASE): _PASSWORD,
            vol.Optional(CONF_SUDO_PASSWORD): _PASSWORD,
            vol.Required(
                CONF_TARGET_USER, default=d.get(CONF_TARGET_USER, "")
            ): str,
        }
    )


_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SSH_PASSWORD): _PASSWORD,
        vol.Optional(CONF_SSH_KEY): _KEY,
        vol.Optional(CONF_SSH_KEY_PASSPHRASE): _PASSWORD,
        vol.Optional(CONF_SUDO_PASSWORD): _PASSWORD,
    }
)


# Linux login names (useradd's default NAME_REGEX, plus upper case and dots
# accepted by some distributions). Must not start with "-": the name is passed
# to the remote ``timekpra`` command line.
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,31}$")


def _check_key(key: str, passphrase: str | None) -> bool:
    """Blocking (bcrypt KDF for encrypted keys): run in the executor."""
    try:
        asyncssh.import_private_key(key, passphrase=passphrase or None)
    except Exception:  # noqa: BLE001 — malformed key, wrong passphrase…
        return False
    return True


async def _validate(hass: HomeAssistant, user_input: dict[str, Any]) -> dict[str, str]:
    """Validate the auth fields locally (no network — stays offline-friendly).

    Returns a mapping of field -> error key (empty when everything is valid).
    """
    errors: dict[str, str] = {}
    # The SSH layer silently strips any other character, so "jean paul"
    # used to manage "jeanpaul" without any warning.
    if not _USERNAME_RE.match(str(user_input.get(CONF_TARGET_USER, ""))):
        errors[CONF_TARGET_USER] = "invalid_user"
    method = user_input.get(CONF_AUTH_METHOD, AUTH_PASSWORD)

    if method == AUTH_PASSWORD:
        if not user_input.get(CONF_SSH_PASSWORD):
            errors[CONF_SSH_PASSWORD] = "password_required"
    else:  # AUTH_KEY
        key = user_input.get(CONF_SSH_KEY, "")
        if not key:
            errors[CONF_SSH_KEY] = "key_required"
        elif not await hass.async_add_executor_job(
            _check_key, key, user_input.get(CONF_SSH_KEY_PASSPHRASE)
        ):
            errors[CONF_SSH_KEY] = "invalid_key"

    return errors


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    """Trim the host fields (" 192.168.1.5" made a second entry)."""
    data = dict(user_input)
    for field in (CONF_SSH_HOST, CONF_SSH_HOST_VPN, CONF_SSH_USER, CONF_TARGET_USER):
        if isinstance(data.get(field), str):
            data[field] = data[field].strip()
    return data


def _keep_secrets(current: Mapping[str, Any], user_input: dict[str, Any]) -> dict[str, Any]:
    """Empty secret field = keep the stored value."""
    data = dict(user_input)
    for field in SECRET_FIELDS:
        if not data.get(field) and current.get(field):
            data[field] = current[field]
    return data


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


def _unique_id(data: Mapping[str, Any]) -> str:
    return f"timekpra_{str(data[CONF_SSH_HOST]).lower()}_{data[CONF_TARGET_USER]}"


class TimekpraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Timekpra."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial configuration step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = _clean(user_input)
            errors = await _validate(self.hass, user_input)
            if not errors:
                await self.async_set_unique_id(_unique_id(user_input))
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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """The machine refused the stored credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Ask for new credentials (empty field = keep the current one)."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _keep_secrets(entry.data, {**entry.data, **user_input})
            errors = await _validate(self.hass, data)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data=_normalize(data)
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={"user": entry.data.get(CONF_TARGET_USER, "")},
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
        """Show the options form pre-filled with current values (no secrets)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = _clean(user_input)
            data = _keep_secrets(
                self.config_entry.data, {**self.config_entry.data, **user_input}
            )
            errors = await _validate(self.hass, data)
            if not errors and any(
                other.entry_id != self.config_entry.entry_id
                and other.unique_id == _unique_id(data)
                for other in self.hass.config_entries.async_entries(DOMAIN)
            ):
                # Same machine + child as another entry: two coordinators
                # would fight over the same Timekpr user.
                errors["base"] = "already_configured"
            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=_normalize(data),
                    title=f"Timekpra - {data[CONF_TARGET_USER]}",
                    unique_id=_unique_id(data),
                )
                return self.async_create_entry(title="", data={})
            defaults = user_input
        else:
            defaults = dict(self.config_entry.data)

        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(defaults),
            errors=errors,
        )
