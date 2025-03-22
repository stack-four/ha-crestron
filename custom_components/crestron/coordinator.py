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

from .api import ApiAuthError, ApiError, CrestronAPI
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


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
                shades = await self.api.get_shades()
                self._shades = shades

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

    async def open_shade(self, shade_id: int) -> bool:
        """Open a shade."""
        shade = self._shades.get(shade_id)
        if not shade:
            _LOGGER.error("Shade %s not found", shade_id)
            return False

        result = await self.api.open_shade(
            shade_id=shade_id,
            shade_name=shade.name,
            room_id=shade.roomId,
        )

        if result:
            # Update local state
            shade.position = OPEN_VALUE

            # Request a refresh to get the latest state
            await self.async_request_refresh()

        return result

    async def close_shade(self, shade_id: int) -> bool:
        """Close a shade."""
        shade = self._shades.get(shade_id)
        if not shade:
            _LOGGER.error("Shade %s not found", shade_id)
            return False

        result = await self.api.close_shade(
            shade_id=shade_id,
            shade_name=shade.name,
            room_id=shade.roomId,
        )

        if result:
            # Update local state
            shade.position = CLOSED_VALUE

            # Request a refresh to get the latest state
            await self.async_request_refresh()

        return result

    async def set_shade_position(self, shade_id: int, position: int) -> bool:
        """Set shade position."""
        shade = self._shades.get(shade_id)
        if not shade:
            _LOGGER.error("Shade %s not found", shade_id)
            return False

        result = await self.api.set_shade_position(
            shade_id=shade_id,
            position=position,
            shade_name=shade.name,
            room_id=shade.roomId,
        )

        if result:
            # Update local state
            shade.position = position

            # Request a refresh to get the latest state
            await self.async_request_refresh()

        return result
