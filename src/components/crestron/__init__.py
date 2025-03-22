"""The Crestron integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any, Dict

import aiohttp
import voluptuous as vol

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


def register_services(hass: HomeAssistant) -> None:
    """Register integration services."""

    async def async_set_position(call: ServiceCall) -> None:
        """Service to set shade position."""
        shade_id = call.data[ATTR_SHADE_ID]
        position = call.data[ATTR_POSITION]

        # Find coordinator with this shade
        for coordinator in hass.data[DOMAIN].values():
            coordinator: CrestronCoordinator
            if shade_id in coordinator.shades:
                # Convert from 0-100 to 0-65535
                raw_position = int(position / 100 * 65535)
                await coordinator.set_shade_position(shade_id, raw_position)
                return

        _LOGGER.error("Shade %s not found", shade_id)

    async def async_open_shade(call: ServiceCall) -> None:
        """Service to open shade."""
        shade_id = call.data[ATTR_SHADE_ID]

        # Find coordinator with this shade
        for coordinator in hass.data[DOMAIN].values():
            coordinator: CrestronCoordinator
            if shade_id in coordinator.shades:
                await coordinator.open_shade(shade_id)
                return

        _LOGGER.error("Shade %s not found", shade_id)

    async def async_close_shade(call: ServiceCall) -> None:
        """Service to close shade."""
        shade_id = call.data[ATTR_SHADE_ID]

        # Find coordinator with this shade
        for coordinator in hass.data[DOMAIN].values():
            coordinator: CrestronCoordinator
            if shade_id in coordinator.shades:
                await coordinator.close_shade(shade_id)
                return

        _LOGGER.error("Shade %s not found", shade_id)

    async def async_stop_shade(call: ServiceCall) -> None:
        """Service to stop shade."""
        shade_id = call.data[ATTR_SHADE_ID]

        # Find coordinator with this shade
        for coordinator in hass.data[DOMAIN].values():
            coordinator: CrestronCoordinator
            if shade_id in coordinator.shades:
                # For now, we'll just set it to the current position to stop it
                shade = coordinator.shades.get(shade_id)
                if shade:
                    await coordinator.set_shade_position(shade_id, shade.position)
                return

        _LOGGER.error("Shade %s not found", shade_id)

    # Register services if they don't already exist
    if not hass.services.has_service(DOMAIN, SERVICE_SET_POSITION):
        hass.services.async_register(
            DOMAIN, SERVICE_SET_POSITION, async_set_position, schema=SET_POSITION_SCHEMA
        )

    if not hass.services.has_service(DOMAIN, SERVICE_OPEN_SHADE):
        hass.services.async_register(
            DOMAIN, SERVICE_OPEN_SHADE, async_open_shade, schema=SHADE_ID_SCHEMA
        )

    if not hass.services.has_service(DOMAIN, SERVICE_CLOSE_SHADE):
        hass.services.async_register(
            DOMAIN, SERVICE_CLOSE_SHADE, async_close_shade, schema=SHADE_ID_SCHEMA
        )

    if not hass.services.has_service(DOMAIN, SERVICE_STOP_SHADE):
        hass.services.async_register(
            DOMAIN, SERVICE_STOP_SHADE, async_stop_shade, schema=SHADE_ID_SCHEMA
        )