"""Crestron data coordinator."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any, Dict, List, Optional, cast

import async_timeout

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.components.cover import ATTR_POSITION, CoverEntityFeature

from .api import ApiAuthError, ApiError, CrestronAPI
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Position values
OPEN_VALUE = 100
CLOSED_VALUE = 0


class CrestronCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Crestron coordinator."""

    def __init__(self, hass: HomeAssistant, api: CrestronAPI):
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api
        self._shades: Dict[int, Dict[str, Any]] = {}

    @property
    def shades(self) -> Dict[int, Dict[str, Any]]:
        """Return cached shades."""
        return self._shades

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"crestron_{self.api.host}"

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from API endpoint."""
        try:
            async with async_timeout.timeout(30):
                # Fetch shades
                shade_states = await self.api.get_shades()

                # Convert to dictionary keyed by ID for easier lookups
                self._shades = {
                    shade.id: {
                        "id": shade.id,
                        "name": shade.name,
                        "position": shade.position,
                        "connection_status": shade.connectionStatus,
                        "room_id": shade.roomId,
                        "type": shade.subType,
                    }
                    for shade in shade_states
                }

                # Return data
                return {
                    "shades": self._shades,
                }
        except ApiAuthError as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except ApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except (asyncio.TimeoutError, Exception) as err:
            raise UpdateFailed(f"Error updating from API: {err}") from err

    def has_shade(self, shade_id: int) -> bool:
        """Check if shade exists."""
        return shade_id in self._shades

    async def open_shade(self, shade_id: int) -> bool:
        """Open a shade."""
        if not self.has_shade(shade_id):
            _LOGGER.error("Shade %s not found", shade_id)
            return False

        try:
            await self.api.set_position(shade_id, OPEN_VALUE)

            # Update local state
            if shade_id in self._shades:
                self._shades[shade_id]["position"] = OPEN_VALUE

            # Request a refresh to get the latest state
            await self.async_request_refresh()
            return True
        except Exception as err:
            _LOGGER.error("Error opening shade %s: %s", shade_id, err)
            return False

    async def close_shade(self, shade_id: int) -> bool:
        """Close a shade."""
        if not self.has_shade(shade_id):
            _LOGGER.error("Shade %s not found", shade_id)
            return False

        try:
            await self.api.set_position(shade_id, CLOSED_VALUE)

            # Update local state
            if shade_id in self._shades:
                self._shades[shade_id]["position"] = CLOSED_VALUE

            # Request a refresh to get the latest state
            await self.async_request_refresh()
            return True
        except Exception as err:
            _LOGGER.error("Error closing shade %s: %s", shade_id, err)
            return False

    async def set_shade_position(self, shade_id: int, position: int) -> bool:
        """Set shade position."""
        if not self.has_shade(shade_id):
            _LOGGER.error("Shade %s not found", shade_id)
            return False

        try:
            await self.api.set_position(shade_id, position)

            # Update local state
            if shade_id in self._shades:
                self._shades[shade_id]["position"] = position

            # Request a refresh to get the latest state
            await self.async_request_refresh()
            return True
        except Exception as err:
            _LOGGER.error("Error setting position for shade %s: %s", shade_id, err)
            return False

    async def stop_shade(self, shade_id: int) -> bool:
        """Stop a shade."""
        if not self.has_shade(shade_id):
            _LOGGER.error("Shade %s not found", shade_id)
            return False

        try:
            await self.api.stop_shade(shade_id)

            # Request a refresh to get the latest state
            await self.async_request_refresh()
            return True
        except Exception as err:
            _LOGGER.error("Error stopping shade %s: %s", shade_id, err)
            return False
