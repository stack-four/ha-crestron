"""Config flow for Crestron integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_TOKEN
import homeassistant.helpers.config_validation as cv

from .api import CrestronAPI
from .const import DOMAIN, LOGGER, CONF_AUTH_TOKEN, CONF_SCAN_INTERVAL


class CrestronConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Crestron shade."""

    VERSION = 1

    def __init__(self) -> None:
        """Handle a config flow for Crestron."""
        self.host: str = ""
        self.auth_token: str = ""
        self.shade_name_given_by_user: str = ""
        self.scan_interval: int = 30

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if user_input:
            self.host = user_input[CONF_HOST]
            if CONF_AUTH_TOKEN in user_input:
                self.auth_token = user_input[CONF_AUTH_TOKEN]

            if CONF_SCAN_INTERVAL in user_input:
                self.scan_interval = user_input[CONF_SCAN_INTERVAL]

            api = CrestronAPI(self.hass, self.host, self.auth_token)

            try:
                # Test connection
                await api.ping()
                if self.auth_token:
                    await api.login()
                initialized = True
                unique_id = f"crestron_{self.host}"  # Create a unique ID based on host

                # Set a default name for the device
                self.shade_name_given_by_user = f"Crestron ({self.host})"

                # Create the config entry
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=self.shade_name_given_by_user,
                    data={
                        CONF_HOST: self.host,
                        CONF_AUTH_TOKEN: self.auth_token,
                        CONF_SCAN_INTERVAL: self.scan_interval,
                    },
                )
            except Exception:
                errors[CONF_HOST] = "cannot_connect"

        # Show user form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Required(CONF_AUTH_TOKEN): cv.string,
                    vol.Optional(CONF_SCAN_INTERVAL, default=30): cv.positive_int,
                },
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
                    "name": f"{self.shade_name_given_by_user}",
                    "host": self.host
                },
                "configuration_url": f"http://{self.host}",
            }
        )

        # Go to confirmation
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle a confirmation flow initiated by zeroconf."""
        errors = {}

        if user_input is not None:
            if CONF_AUTH_TOKEN in user_input:
                self.auth_token = user_input[CONF_AUTH_TOKEN]

            if CONF_SCAN_INTERVAL in user_input:
                self.scan_interval = user_input[CONF_SCAN_INTERVAL]

            api = CrestronAPI(self.hass, self.host, self.auth_token)

            try:
                # Test connection with auth
                await api.ping()
                await api.login()

                return self.async_create_entry(
                    title=self.shade_name_given_by_user,
                    data={
                        CONF_HOST: self.host,
                        CONF_AUTH_TOKEN: self.auth_token,
                        CONF_SCAN_INTERVAL: self.scan_interval,
                    },
                )
            except Exception:
                errors[CONF_AUTH_TOKEN] = "invalid_auth"

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": self.shade_name_given_by_user,
                "host": self.host,
            },
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AUTH_TOKEN): cv.string,
                    vol.Optional(CONF_SCAN_INTERVAL, default=30): cv.positive_int,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation."""
        errors = {}

        if user_input is not None:
            self.auth_token = user_input[CONF_AUTH_TOKEN]
            entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

            if entry:
                self.host = entry.data[CONF_HOST]
                api = CrestronAPI(self.hass, self.host, self.auth_token)

                try:
                    # Test connection with new auth token
                    await api.ping()
                    await api.login()

                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={
                            **entry.data,
                            CONF_AUTH_TOKEN: self.auth_token
                        }
                    )
                    return self.async_abort(reason="reauth_successful")
                except Exception:
                    errors[CONF_AUTH_TOKEN] = "invalid_auth"

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={"host": self.host},
            data_schema=vol.Schema({vol.Required(CONF_AUTH_TOKEN): cv.string}),
            errors=errors,
        )

