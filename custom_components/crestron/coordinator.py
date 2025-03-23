"""Crestron data coordinator."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any, Dict

import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed


from .api import (
    ApiAuthError,
    ApiError,
    ApiConnectionError,
    ApiTimeoutError,
    CrestronAPI,
    HA_OPEN_VALUE,
    HA_CLOSED_VALUE,
    convert_position_to_ha,
    convert_position_from_ha
)
from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class CrestronCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Crestron coordinator."""

    def __init__(self, hass: HomeAssistant, api: CrestronAPI, entry_options: Dict[str, Any]):
        """Initialize coordinator."""
        # Get scan interval from options or use default
        scan_interval = entry_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self._shades: Dict[int, Dict[str, Any]] = {}
        self._last_update_success = False
        self._is_connected = False
        self._connection_errors = 0
        self._max_connection_errors = 3

    @property
    def shades(self) -> Dict[int, Dict[str, Any]]:
        """Return cached shades."""
        return self._shades

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"crestron_{self.api.host}"

    @property
    def is_connected(self) -> bool:
        """Return if api is connected."""
        return self._is_connected

    @property
    def last_update_success(self) -> bool:
        """Return if last update was successful."""
        return self._last_update_success

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from API endpoint."""
        try:
            async with async_timeout.timeout(30):
                # First try to ping to check connectivity
                try:
                    if not await self.api.ping():
                        self._connection_errors += 1
                        if self._connection_errors >= self._max_connection_errors:
                            self._is_connected = False
                            _LOGGER.warning(
                                "Failed to ping Crestron API after %s attempts",
                                self._connection_errors
                            )
                        raise ApiConnectionError("Failed to ping API")
                    else:
                        # Reset error counter on successful ping
                        self._connection_errors = 0
                        self._is_connected = True
                except (ApiConnectionError, ApiTimeoutError) as err:
                    self._connection_errors += 1
                    if self._connection_errors >= self._max_connection_errors:
                        self._is_connected = False
                    _LOGGER.debug("Ping failed: %s", err)
                    raise

                # Fetch shades
                shade_states = await self.api.get_shades()

                # Convert to dictionary keyed by ID for easier lookups
                self._shades = {
                    shade.id: {
                        "id": shade.id,
                        "name": shade.name,
                        "position": convert_position_to_ha(shade.position),
                        "connection_status": shade.connectionStatus,
                        "room_id": shade.roomId,
                        "type": shade.subType,
                    }
                    for shade in shade_states
                }

                # If we got here, update was successful
                if not self._last_update_success:
                    _LOGGER.info("Connection to Crestron API restored")
                self._last_update_success = True
                self._is_connected = True
                self._connection_errors = 0

                # Return data
                return {
                    "shades": self._shades,
                    "connected": self._is_connected,
                }
        except ApiAuthError as err:
            self._last_update_success = False
            self._is_connected = False
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except ApiConnectionError as err:
            self._last_update_success = False
            self._connection_errors += 1
            if self._connection_errors >= self._max_connection_errors:
                self._is_connected = False
                _LOGGER.error(
                    "Connection lost to Crestron API after %s consecutive errors",
                    self._connection_errors
                )
            _LOGGER.error("Connection error during update: %s", err)
            raise UpdateFailed(f"Error connecting to API: {err}") from err
        except ApiTimeoutError as err:
            self._last_update_success = False
            self._connection_errors += 1
            if self._connection_errors >= self._max_connection_errors:
                self._is_connected = False
            _LOGGER.error("Timeout during update: %s", err)
            raise UpdateFailed(f"Timeout connecting to API: {err}") from err
        except ApiError as err:
            self._last_update_success = False
            _LOGGER.error("API error during update: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except asyncio.TimeoutError as err:
            self._last_update_success = False
            self._connection_errors += 1
            if self._connection_errors >= self._max_connection_errors:
                self._is_connected = False
            _LOGGER.error("Async timeout during update: %s", err)
            raise UpdateFailed(f"Timeout during update: {err}") from err
        except Exception as err:
            self._last_update_success = False
            _LOGGER.exception("Unexpected error during update: %s", err)
            raise UpdateFailed(f"Unexpected error: {err}") from err

    def has_shade(self, shade_id: int) -> bool:
        """Check if shade exists."""
        return shade_id in self._shades

    async def open_shade(self, shade_id: int) -> bool:
        """Open a shade."""
        if not self.has_shade(shade_id):
            _LOGGER.error("Shade %s not found", shade_id)
            return False

        try:
            result = await self.api.open_shade(shade_id)

            # Update local state immediately on success
            if result and shade_id in self._shades:
                self._shades[shade_id]["position"] = HA_OPEN_VALUE
                self.async_set_updated_data({"shades": self._shades})
                _LOGGER.debug("Successfully opened shade %s", shade_id)

            # Schedule refresh to get the latest state
            await self.async_request_refresh()
            return result
        except ApiConnectionError as err:
            _LOGGER.error("Connection error opening shade %s: %s", shade_id, err)
            return False
        except ApiTimeoutError as err:
            _LOGGER.error("Timeout opening shade %s: %s", shade_id, err)
            return False
        except ApiAuthError as err:
            _LOGGER.error("Authentication error opening shade %s: %s", shade_id, err)
            # Trigger a full refresh to re-authenticate
            self.async_set_updated_data(None)
            await self.async_request_refresh()
            return False
        except Exception as err:
            _LOGGER.error("Error opening shade %s: %s", shade_id, err)
            return False

    async def close_shade(self, shade_id: int) -> bool:
        """Close a shade."""
        if not self.has_shade(shade_id):
            _LOGGER.error("Shade %s not found", shade_id)
            return False

        try:
            result = await self.api.close_shade(shade_id)

            # Update local state immediately on success
            if result and shade_id in self._shades:
                self._shades[shade_id]["position"] = HA_CLOSED_VALUE
                self.async_set_updated_data({"shades": self._shades})
                _LOGGER.debug("Successfully closed shade %s", shade_id)

            # Schedule refresh to get the latest state
            await self.async_request_refresh()
            return result
        except ApiConnectionError as err:
            _LOGGER.error("Connection error closing shade %s: %s", shade_id, err)
            return False
        except ApiTimeoutError as err:
            _LOGGER.error("Timeout closing shade %s: %s", shade_id, err)
            return False
        except ApiAuthError as err:
            _LOGGER.error("Authentication error closing shade %s: %s", shade_id, err)
            # Trigger a full refresh to re-authenticate
            self.async_set_updated_data(None)
            await self.async_request_refresh()
            return False
        except Exception as err:
            _LOGGER.error("Error closing shade %s: %s", shade_id, err)
            return False

    async def set_shade_position(self, shade_id: int, position: int) -> bool:
        """Set shade position."""
        if not self.has_shade(shade_id):
            _LOGGER.error("Shade %s not found", shade_id)
            return False

        try:
            # Convert from Home Assistant position (0-100) to Crestron position (0-65535)
            crestron_position = convert_position_from_ha(position)
            result = await self.api.set_position(shade_id, crestron_position)

            # Update local state immediately on success
            if result and shade_id in self._shades:
                self._shades[shade_id]["position"] = position
                self.async_set_updated_data({"shades": self._shades})
                _LOGGER.debug("Successfully set position for shade %s to %s", shade_id, position)

            # Schedule refresh to get the latest state
            await self.async_request_refresh()
            return result
        except ApiConnectionError as err:
            _LOGGER.error("Connection error setting position for shade %s: %s", shade_id, err)
            return False
        except ApiTimeoutError as err:
            _LOGGER.error("Timeout setting position for shade %s: %s", shade_id, err)
            return False
        except ApiAuthError as err:
            _LOGGER.error("Authentication error setting position for shade %s: %s", shade_id, err)
            # Trigger a full refresh to re-authenticate
            self.async_set_updated_data(None)
            await self.async_request_refresh()
            return False
        except Exception as err:
            _LOGGER.error("Error setting position for shade %s: %s", shade_id, err)
            return False

    async def stop_shade(self, shade_id: int) -> bool:
        """Stop a shade."""
        if not self.has_shade(shade_id):
            _LOGGER.error("Shade %s not found", shade_id)
            return False

        try:
            result = await self.api.stop_shade(shade_id)

            # Update UI immediately to indicate the shade has stopped
            if result and shade_id in self._shades:
                self.async_set_updated_data({"shades": self._shades})
                _LOGGER.debug("Successfully stopped shade %s", shade_id)

            # Schedule refresh to get the latest state
            await self.async_request_refresh()
            return result
        except ApiConnectionError as err:
            _LOGGER.error("Connection error stopping shade %s: %s", shade_id, err)
            return False
        except ApiTimeoutError as err:
            _LOGGER.error("Timeout stopping shade %s: %s", shade_id, err)
            return False
        except ApiAuthError as err:
            _LOGGER.error("Authentication error stopping shade %s: %s", shade_id, err)
            # Trigger a full refresh to re-authenticate
            self.async_set_updated_data(None)
            await self.async_request_refresh()
            return False
        except Exception as err:
            _LOGGER.error("Error stopping shade %s: %s", shade_id, err)
            return False
