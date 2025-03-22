"""The Crestron integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, Dict

import aiohttp
import voluptuous as vol
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_SCAN_INTERVAL,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import UpdateFailed

from .api import ApiAuthError, ApiError, CrestronAPI
from .const import (
    ATTR_POSITION,
    ATTR_SHADE_ID,
    CONF_AUTH_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SERVICE_CLOSE_SHADE,
    SERVICE_OPEN_SHADE,
    SERVICE_SET_POSITION,
    SERVICE_STOP_SHADE,
    _LOGGER,
)
from .coordinator import CrestronCoordinator
from .repairs import (
    ISSUE_AUTH_FAILURE,
    ISSUE_CONNECTIVITY,
    async_create_issue,
    register_repair_flows,
)

PLATFORMS = [Platform.COVER]

# Service schemas
SET_POSITION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_SHADE_ID): cv.positive_int,
        vol.Required(ATTR_POSITION): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
    }
)

SHADE_ID_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_SHADE_ID): cv.positive_int,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Crestron integration."""
    hass.data[DOMAIN] = {}

    # Register repair flows
    register_repair_flows(hass)

    return True


def register_services(hass: HomeAssistant) -> None:
    """Register Crestron services."""

    async def set_position(call: ServiceCall) -> None:
        """Set shade position."""
        shade_id = call.data[ATTR_SHADE_ID]
        position = call.data[ATTR_POSITION]

        # Find coordinator that contains this shade
        for entry_id, coordinator in hass.data[DOMAIN].items():
            if coordinator.api.has_shade(shade_id):
                await coordinator.api.set_position(shade_id, position)
                return

        _LOGGER.error("Could not find shade with ID %s", shade_id)

    async def open_shade(call: ServiceCall) -> None:
        """Open shade."""
        shade_id = call.data[ATTR_SHADE_ID]

        # Find coordinator that contains this shade
        for entry_id, coordinator in hass.data[DOMAIN].items():
            if coordinator.api.has_shade(shade_id):
                await coordinator.api.open_shade(shade_id)
                return

        _LOGGER.error("Could not find shade with ID %s", shade_id)

    async def close_shade(call: ServiceCall) -> None:
        """Close shade."""
        shade_id = call.data[ATTR_SHADE_ID]

        # Find coordinator that contains this shade
        for entry_id, coordinator in hass.data[DOMAIN].items():
            if coordinator.api.has_shade(shade_id):
                await coordinator.api.close_shade(shade_id)
                return

        _LOGGER.error("Could not find shade with ID %s", shade_id)

    async def stop_shade(call: ServiceCall) -> None:
        """Stop shade."""
        shade_id = call.data[ATTR_SHADE_ID]

        # Find coordinator that contains this shade
        for entry_id, coordinator in hass.data[DOMAIN].items():
            if coordinator.api.has_shade(shade_id):
                await coordinator.api.stop_shade(shade_id)
                return

        _LOGGER.error("Could not find shade with ID %s", shade_id)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_POSITION, set_position, schema=SET_POSITION_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_OPEN_SHADE, open_shade, schema=SHADE_ID_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLOSE_SHADE, close_shade, schema=SHADE_ID_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_STOP_SHADE, stop_shade, schema=SHADE_ID_SCHEMA
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Crestron from a config entry."""
    try:
        # Get configuration
        host = entry.data[CONF_HOST]
        auth_token = entry.data[CONF_AUTH_TOKEN]
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        # Create API client
        api = CrestronAPI(
            hass=hass,
            host=host,
            auth_token=auth_token,
        )

        # Verify that we can connect
        try:
            await api.ping()
            await api.login()
        except ApiAuthError as err:
            # Create an issue for the user
            async_create_issue(
                hass=hass,
                issue_id=ISSUE_AUTH_FAILURE,
                entry=entry,
                description_placeholders={"host": host},
            )
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except (ApiError, asyncio.TimeoutError, aiohttp.ClientError) as err:
            # Create an issue for the user
            async_create_issue(
                hass=hass,
                issue_id=ISSUE_CONNECTIVITY,
                entry=entry,
                description_placeholders={"host": host},
            )
            raise ConfigEntryNotReady(f"Failed to connect to {host}") from err

        # Create update coordinator
        coordinator = CrestronCoordinator(hass, api)

        # Initial data fetch
        await coordinator.async_config_entry_first_refresh()

        # Store coordinator
        hass.data[DOMAIN][entry.entry_id] = coordinator

        # Set up platforms
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        # Register services
        register_services(hass)

        return True

    except Exception as err:
        _LOGGER.exception("Error setting up Crestron integration: %s", err)
        raise ConfigEntryNotReady(f"Error setting up Crestron integration: {err}") from err


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Remove coordinator from hass data
        hass.data[DOMAIN].pop(entry.entry_id)

        # Remove services if no config entries left
        if not hass.data[DOMAIN]:
            for service in [
                SERVICE_SET_POSITION,
                SERVICE_OPEN_SHADE,
                SERVICE_CLOSE_SHADE,
                SERVICE_STOP_SHADE,
            ]:
                if hass.services.has_service(DOMAIN, service):
                    hass.services.async_remove(DOMAIN, service)

    return unload_ok