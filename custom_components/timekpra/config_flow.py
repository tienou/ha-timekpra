"""Config flow for the Timekpra integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_ADMIN_PASSWORD,
    CONF_ADMIN_USER,
    CONF_SSH_HOST,
    CONF_SSH_PASSWORD,
    CONF_SSH_PORT,
    CONF_SSH_USER,
    CONF_TARGET_USER,
    DOMAIN,
)
from .ssh import TimekpraSSH

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SSH_HOST): str,
        vol.Required(CONF_SSH_PORT, default=22): int,
        vol.Required(CONF_SSH_USER): str,
        vol.Required(CONF_SSH_PASSWORD): str,
        vol.Required(CONF_TARGET_USER, default="camille"): str,
        vol.Optional(CONF_ADMIN_USER): str,
        vol.Optional(CONF_ADMIN_PASSWORD): str,
    }
)


class TimekpraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Timekpra."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Use admin credentials for SSH if provided, otherwise ssh creds
            ssh_user = user_input.get(CONF_ADMIN_USER) or user_input[CONF_SSH_USER]
            ssh_pass = user_input.get(CONF_ADMIN_PASSWORD) or user_input[CONF_SSH_PASSWORD]
            ssh = TimekpraSSH(
                host=user_input[CONF_SSH_HOST],
                port=user_input[CONF_SSH_PORT],
                username=ssh_user,
                password=ssh_pass,
                sudo_password=user_input.get(CONF_ADMIN_PASSWORD),
            )

            if not await ssh.test_connection():
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    f"timekpra_{user_input[CONF_SSH_HOST]}_{user_input[CONF_TARGET_USER]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Timekpra - {user_input[CONF_TARGET_USER]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
