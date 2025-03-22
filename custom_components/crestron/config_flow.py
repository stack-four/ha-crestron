"""Config flow for Crestron integration."""

from __future__ import annotations

import crestron
import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_TOKEN
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, LOGGER


class CrestronConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Crestron shade."""

    VERSION = 1

    def __init__(self) -> None:
        """Handle a config flow for Crestron."""
        self.host: str = ""
        self.authToken: str = ""
        self.shade_name_given_by_user: str = ""

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if user_input:
            self.host = user_input[CONF_HOST]

            new_crestron = await crestron.new_client(self.host, "")

            if not new_crestron.is_initialized:
                errors[CONF_HOST] = "cannot_connect"
            else:
                await self.async_set_unique_id(new_crestron.unique_id)
                self._abort_if_unique_id_configured()

                self.shade_name_given_by_user = new_crestron.user_name

                if not new_crestron.is_unlocked:
                    return await self.async_step_password()
                return await self._async_step_finish_config()

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
        """Unlock the robots local http interface with authToken."""
        errors: dict[str, str] = {}

        if user_input:
            self.authToken = user_input[CONF_TOKEN]
            new_crestron = await crestron.create_client(self.host, self.authToken)

            if not new_crestron.is_initialized:
                errors[CONF_TOKEN] = "cannot_connect"
            elif not new_crestron.is_unlocked:
                errors[CONF_TOKEN] = "invalid_auth"

            if not errors:
                return await self._async_step_finish_config()

        return self.async_show_form(
            step_id="authToken",
            data_schema=vol.Schema(
                {vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(8))},
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""

        LOGGER.debug("Zeroconf discovery_info: %s", discovery_info)

        # connect and gather information from your ROMY
        self.host = discovery_info.host
        LOGGER.debug("ZeroConf Host: %s", self.host)

        new_discovered_crestron = await crestron.create_client(self.host, "")

        self.shade_name_given_by_user = new_discovered_crestron.user_name
        LOGGER.debug("ZeroConf Name: %s", self.shade_name_given_by_user)

        # get unique id and stop discovery if robot is already added
        unique_id = new_discovered_crestron.unique_id
        LOGGER.debug("ZeroConf Unique_id: %s", unique_id)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        self.context.update(
            {
                "title_placeholders": {
                    "name": f"{self.shade_name_given_by_user} ({self.host} / {unique_id})"
                },
                "configuration_url": f"http://{self.host}:{new_discovered_crestron.port}",
            }
        )

        # if robot got already unlocked with authToken add it directly
        if not new_discovered_crestron.is_initialized:
            return self.async_abort(reason="cannot_connect")

        if new_discovered_crestron.is_unlocked:
            return await self.async_step_zeroconf_confirm()

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
                CONF_TOKEN: self.authToken,
            },
        )
