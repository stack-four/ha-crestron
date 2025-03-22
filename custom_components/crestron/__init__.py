"""The Crestron integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, Dict
import logging

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

from .const import (
    ATTR_POSITION,
    ATTR_SHADE_ID,
    CONF_AUTH_TOKEN,
    CONF_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MANUFACTURER,
    SERVICE_CLOSE_SHADE,
    SERVICE_OPEN_SHADE,
    SERVICE_SET_POSITION,
    SERVICE_STOP_SHADE,
    _LOGGER,
)
from .repairs import (
    ISSUE_AUTH_FAILURE,
    ISSUE_CONNECTIVITY,
    async_create_issue,
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

    # Initialize the domain data
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

        # Merge options with data for backwards compatibility
        entry_options = dict(entry.options)

        # Import API client here to avoid blocking at module load time
        import aiohttp
        from .api import CrestronAPI, ApiAuthError, ApiError
        from .coordinator import CrestronCoordinator
        from homeassistant.helpers.update_coordinator import UpdateFailed

        # Create API client
        api = CrestronAPI(
            hass=hass,
            host=host,
            auth_token=auth_token,
        )

        # Verify that we can connect
        try:
            await api.ping()
        except ApiAuthError as err:
            _LOGGER.error("Authentication failed: %s", err)
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except (ApiError, asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Failed to connect to %s: %s", host, err)
            raise ConfigEntryNotReady(f"Failed to connect to {host}") from err

        # Create the hub device with the correct identifier format
        device_registry = dr.async_get(hass)

        # Check for existing hub device with our format
        existing_hub_id = None
        for device in device_registry.devices.values():
            if any(identifier[0] == DOMAIN and
                   (identifier[1] == f"crestron_{host}" or
                    identifier[1].startswith(f"crestron_{host}:"))
                   for identifier in device.identifiers):
                # Found existing hub with correct format
                existing_hub_id = next(identifier[1] for identifier in device.identifiers
                                     if identifier[0] == DOMAIN)
                _LOGGER.debug("Found existing hub device with ID: %s", existing_hub_id)
                break

        # If no existing hub found, use the consistent format
        if not existing_hub_id:
            existing_hub_id = f"crestron_{host}"

        # Create or update the hub device
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, existing_hub_id)},
            manufacturer=MANUFACTURER,
            name=f"Crestron Controller ({host})",
            model="Crestron Shade Controller",
        )

        # Create update coordinator
        coordinator = CrestronCoordinator(hass, api, entry_options)

        # Initial data fetch
        try:
            await coordinator.async_config_entry_first_refresh()
        except (ApiError, asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Failed to fetch initial data from %s: %s", host, err)
            raise ConfigEntryNotReady(f"Failed to fetch initial data from {host}") from err

        # Store coordinator
        hass.data[DOMAIN][entry.entry_id] = coordinator

        # Set up platforms
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        # Register services if not already registered
        if len(hass.data[DOMAIN]) == 1:  # First entry
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