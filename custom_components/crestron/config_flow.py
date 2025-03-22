"""Config flow for Crestron integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_TOKEN
import homeassistant.helpers.config_validation as cv

from .api import CrestronAPI
from .const import DOMAIN, LOGGER, CONF_AUTH_TOKEN


class CrestronConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Crestron shade."""

    VERSION = 1

    def __init__(self) -> None:
        """Handle a config flow for Crestron."""
        self.host: str = ""
        self.auth_token: str = ""
        self.shade_name_given_by_user: str = ""

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if user_input:
            self.host = user_input[CONF_HOST]

            api = CrestronAPI(self.hass, self.host, "")

            try:
                # Test connection
                await api.ping()
                initialized = True
                unique_id = f"crestron_{self.host}"  # Create a unique ID based on host
                is_unlocked = False  # We'll check auth in the next step

                # Set a default name for the device
                self.shade_name_given_by_user = f"Crestron ({self.host})"

            except Exception:
                initialized = False

            if not initialized:
                errors[CONF_HOST] = "cannot_connect"
            else:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                # Always go to the password step
                return await self.async_step_password()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): cv.string,
                },
            ),
            errors=errors,
        )

    async def async_step_password(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Unlock the Crestron API with auth token."""
        errors: dict[str, str] = {}

        if user_input:
            self.auth_token = user_input[CONF_TOKEN]
            api = CrestronAPI(self.hass, self.host, self.auth_token)

            try:
                # Test connection with auth token
                await api.ping()
                await api.login()
                initialized = True
                is_unlocked = True
            except Exception:
                initialized = False
                is_unlocked = False

            if not initialized:
                errors[CONF_TOKEN] = "cannot_connect"
            elif not is_unlocked:
                errors[CONF_TOKEN] = "invalid_auth"

            if not errors:
                return await self._async_step_finish_config()

        return self.async_show_form(
            step_id="password",
            data_schema=vol.Schema(
                {vol.Required(CONF_TOKEN): cv.string},
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""

        LOGGER.debug("Zeroconf discovery_info: %s", discovery_info)

        # Get host from discovery info
        self.host = discovery_info.host
        LOGGER.debug("ZeroConf Host: %s", self.host)

        # Create a unique ID and set default name
        unique_id = f"crestron_{self.host}"
        self.shade_name_given_by_user = f"Crestron ({self.host})"

        # Set unique ID
        LOGGER.debug("ZeroConf Unique_id: %s", unique_id)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        self.context.update(
            {
                "title_placeholders": {
                    "name": f"{self.shade_name_given_by_user}"
                },
                "configuration_url": f"http://{self.host}",
            }
        )

        # Always require authentication
        return await self.async_step_password()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle a confirmation flow initiated by zeroconf."""
        if user_input is None:
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={
                    "name": self.shade_name_given_by_user,
                    "host": self.host,
                },
            )
        return await self._async_step_finish_config()

    async def _async_step_finish_config(self) -> ConfigFlowResult:
        """Finish the configuration setup."""
        return self.async_create_entry(
            title=self.shade_name_given_by_user,
            data={
                CONF_HOST: self.host,
                CONF_AUTH_TOKEN: self.auth_token,
            },
        )

