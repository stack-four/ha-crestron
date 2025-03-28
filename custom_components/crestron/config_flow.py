"""Config flow for Crestron integration."""

from __future__ import annotations

import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import CONF_AUTH_TOKEN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_AUTH_TOKEN): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    # Import here to avoid blocking at module load time
    from .api import CrestronAPI, ApiAuthError, ApiError

    api = CrestronAPI(
        hass=hass,
        host=data[CONF_HOST],
        auth_token=data[CONF_AUTH_TOKEN],
    )

    await api.ping()

    # Return validated data
    return {"title": f"Crestron ({data[CONF_HOST]})"}


class CrestronConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Crestron."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.discovery_info = None
        self.entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        # Import here to avoid blocking at module load time
        from .api import ApiAuthError, ApiError

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(f"crestron_{user_input[CONF_HOST]}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)
            except ApiAuthError:
                errors["base"] = "invalid_auth"
            except (ApiError, Exception):
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: dict[str, Any]
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        # Get host from discovery
        host = discovery_info.get("host", "")
        unique_id = f"crestron_{host}"

        # Set unique ID
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # Store for the next step
        self.discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": f"Crestron ({host})"}

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by zeroconf."""
        # Import here to avoid blocking at module load time
        from .api import ApiAuthError, ApiError

        if not self.discovery_info:
            return self.async_abort(reason="unknown")

        host = self.discovery_info.get("host", "")

        if user_input is not None:
            try:
                user_input[CONF_HOST] = host
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except ApiAuthError:
                return self.async_show_form(
                    step_id="zeroconf_confirm",
                    data_schema=vol.Schema({
                        vol.Required(CONF_AUTH_TOKEN): str,
                        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
                    }),
                    errors={"base": "invalid_auth"},
                    description_placeholders={"host": host},
                )
            except (ApiError, Exception):
                return self.async_show_form(
                    step_id="zeroconf_confirm",
                    data_schema=vol.Schema({
                        vol.Required(CONF_AUTH_TOKEN): str,
                        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
                    }),
                    errors={"base": "cannot_connect"},
                    description_placeholders={"host": host},
                )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_AUTH_TOKEN): str,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
            }),
            description_placeholders={"host": host},
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Handle reauth when auth is invalid."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauth confirmation."""
        # Import here to avoid blocking at module load time
        from .api import ApiAuthError, ApiError

        errors = {}

        if user_input is not None and self.entry:
            host = self.entry.data[CONF_HOST]
            scan_interval = self.entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

            try:
                # Create new data with existing host but new auth token
                data = {
                    CONF_HOST: host,
                    CONF_AUTH_TOKEN: user_input[CONF_AUTH_TOKEN],
                    CONF_SCAN_INTERVAL: scan_interval
                }

                # Validate
                await validate_input(self.hass, data)

                # Update the config entry
                self.hass.config_entries.async_update_entry(
                    self.entry, data=data
                )

                # Reload the config entry
                await self.hass.config_entries.async_reload(self.entry.entry_id)

                return self.async_abort(reason="reauth_successful")
            except ApiAuthError:
                errors["base"] = "invalid_auth"
            except (ApiError, Exception):
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_AUTH_TOKEN): str}),
            errors=errors,
            description_placeholders={"host": self.entry.data.get(CONF_HOST) if self.entry else "unknown"},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Create the options flow."""
        return CrestronOptionsFlow(config_entry)


class CrestronOptionsFlow(OptionsFlow):
    """Handle Crestron options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.entry_id = config_entry.entry_id
        self.entry_data = dict(config_entry.data)
        self.entry_options = dict(config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.entry_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): int,
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )

