"""Crestron API client."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, cast
import aiohttp
import asyncio
import time

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api_errors import ApiAuthError, ApiConnectionError, ApiError, ApiTimeoutError

_LOGGER = logging.getLogger(__name__)

API_AUTH_TOKEN_HEADER = "Crestron-RestAPI-AuthToken"
API_AUTH_KEY_HEADER = "Crestron-RestAPI-AuthKey"

# Define position values
OPEN_VALUE = 65535  # Full open position in Crestron
CLOSED_VALUE = 0    # Full closed position in Crestron
HA_OPEN_VALUE = 100 # Full open position in Home Assistant
HA_CLOSED_VALUE = 0 # Full closed position in Home Assistant

# Constants for retry logic
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


def convert_position_to_ha(crestron_position: int) -> int:
    """Convert Crestron position (0-65535) to Home Assistant position (0-100)."""
    if crestron_position <= CLOSED_VALUE:
        return HA_CLOSED_VALUE
    if crestron_position >= OPEN_VALUE:
        return HA_OPEN_VALUE

    # Convert from Crestron scale to HA scale
    return round((crestron_position / OPEN_VALUE) * HA_OPEN_VALUE)


def convert_position_from_ha(ha_position: int) -> int:
    """Convert Home Assistant position (0-100) to Crestron position (0-65535)."""
    if ha_position <= HA_CLOSED_VALUE:
        return CLOSED_VALUE
    if ha_position >= HA_OPEN_VALUE:
        return OPEN_VALUE

    # Convert from HA scale to Crestron scale
    return round((ha_position / HA_OPEN_VALUE) * OPEN_VALUE)


class ShadeState:
    """Shade state class."""

    def __init__(
        self,
        position: int,
        id: int,
        name: str,
        subType: str = "Shade",
        connectionStatus: str = "online",
        roomId: int = 0,
    ):
        """Initialize shade state."""
        self.position = position
        self.id = id
        self.name = name
        self.subType = subType
        self.connectionStatus = connectionStatus
        self.roomId = roomId

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ShadeState:
        """Create shade state from dictionary."""
        return cls(
            position=data.get("position", 0),
            id=data.get("id", 0),
            name=data.get("name", "Unknown"),
            subType=data.get("subType", "Shade"),
            connectionStatus=data.get("connectionStatus", "online"),
            roomId=data.get("roomId", 0),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "position": self.position,
            "id": self.id,
            "name": self.name,
            "subType": self.subType,
            "connectionStatus": self.connectionStatus,
            "roomId": self.roomId,
        }


class CrestronAPI:
    """Crestron API client."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        auth_token: str,
    ):
        """Initialize API client."""
        self._hass = hass
        self._session = async_get_clientsession(hass)
        self._host = host
        self._auth_token = auth_token
        self._auth_key = None
        self._base_url = f"http://{host}/cws/api"
        self.shades: Dict[int, Dict[str, Any]] = {}
        self._is_connected = False
        self._connection_lock = asyncio.Lock()
        self._login_lock = asyncio.Lock()
        self._auth_expiry = 0

    @property
    def host(self) -> str:
        """Return host."""
        return self._host

    @property
    def auth_token(self) -> str:
        """Return auth token."""
        return self._auth_token

    async def login(self) -> None:
        """Log in to API and get an auth token."""
        if self._auth_key and self._is_auth_valid():
            _LOGGER.debug("Using existing valid auth key")
            return

        async with self._login_lock:
            # Check again in case another task got the lock first and already logged in
            if self._auth_key and self._is_auth_valid():
                _LOGGER.debug("Another task already performed login")
                return

            _LOGGER.info("Logging in to Crestron API at %s", self._host)
            try:
                timeout = aiohttp.ClientTimeout(total=30)
                async with self._session.post(
                    f"{self._base_url}/login",
                    json={"authToken": self._auth_token},
                    timeout=timeout,
                ) as response:
                    if response.status == 200:
                        response_json = await response.json()
                        self._auth_key = response_json.get("authKey")
                        self._auth_expiry = time.time() + 3600  # Auth valid for 1 hour
                        _LOGGER.info("Successfully logged in to Crestron API")
                    else:
                        error_text = await response.text()
                        _LOGGER.error(
                            "Failed to log in: HTTP %s - %s", response.status, error_text
                        )
                        raise ApiAuthError(f"Login failed: HTTP {response.status}")
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                _LOGGER.error("Connection error during login: %s", err)
                raise ApiConnectionError(f"Connection error during login: {err}") from err

    async def _execute_with_retry(self, func):
        """Execute a function with retry for auth errors."""
        _LOGGER.debug("Executing API request with retry capability")
        retries = 0

        while retries <= MAX_RETRIES:
            try:
                if retries > 0:
                    _LOGGER.debug("Retry attempt %s of %s", retries, MAX_RETRIES)
                    # Add delay between retries (except for the first attempt)
                    await asyncio.sleep(RETRY_DELAY)

                return await func()

            except ApiAuthError as err:
                _LOGGER.info("Auth error, attempting to re-login (retry %s of %s)",
                             retries, MAX_RETRIES)
                retries += 1

                try:
                    await self.login()
                    _LOGGER.info("Re-login successful, retrying operation")
                except ApiAuthError as login_err:
                    _LOGGER.error("Re-login failed: %s", login_err)
                    # No point retrying if we can't log in
                    raise
                except Exception as login_err:
                    _LOGGER.error("Error during re-login: %s", login_err)
                    raise ApiAuthError("Failed to re-login") from login_err

            except (aiohttp.ClientConnectionError, aiohttp.ServerDisconnectedError) as err:
                _LOGGER.warning(
                    "Connection error (retry %s of %s): %s", retries, MAX_RETRIES, err
                )
                retries += 1
                if retries > MAX_RETRIES:
                    _LOGGER.error("Max retries reached for connection error")
                    raise ApiConnectionError(f"Connection error after {MAX_RETRIES} retries: {err}") from err

            except asyncio.TimeoutError as err:
                _LOGGER.warning(
                    "Timeout error (retry %s of %s): %s", retries, MAX_RETRIES, err
                )
                retries += 1
                if retries > MAX_RETRIES:
                    _LOGGER.error("Max retries reached for timeout error")
                    raise ApiTimeoutError(f"Timeout after {MAX_RETRIES} retries") from err

        _LOGGER.error("Exceeded maximum retries")
        raise ApiError("Exceeded maximum retries")

    async def ping(self) -> bool:
        """Ping the API to verify connectivity."""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            _LOGGER.debug("Pinging Crestron API at %s", self._host)
            async with self._session.get(
                f"{self._base_url}",
                headers=self._get_headers(),
                timeout=timeout,
            ) as response:
                if response.status == 200:
                    # Connection is good
                    _LOGGER.debug("Ping successful - connection is active")
                    return True
                elif response.status == 401:
                    # Auth issue, try login
                    _LOGGER.info("Authentication expired, attempting to re-login")
                    try:
                        await self.login()
                        _LOGGER.info("Re-login successful")
                        return True
                    except Exception as err:
                        _LOGGER.error("Failed to re-login after auth error: %s", err)
                        return False
                else:
                    # Other status code
                    _LOGGER.error(
                        "Failed to ping API: HTTP %s - %s",
                        response.status,
                        await response.text(),
                    )
                    return False
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Failed to ping API: %s", err)
            # Force reconnection attempt on next call
            self._auth_key = None
            return False

    async def get_devices(self) -> List[Dict[str, Any]]:
        """Get all devices."""
        async def _get_devices():
            try:
                response = await self._session.get(
                    f"{self._base_url}/devices",
                    headers={API_AUTH_KEY_HEADER: self._auth_key},
                    raise_for_status=True,
                    timeout=30,  # Add explicit timeout
                )
                data = await response.json()
                return data.get("devices", [])
            except aiohttp.ClientResponseError as err:
                if err.status == 401:
                    self._auth_key = None
                    self._is_connected = False
                    raise ApiAuthError("Invalid auth key") from err
                raise ApiError(f"Error getting devices: {err}") from err
            except (aiohttp.ClientConnectionError, aiohttp.ServerDisconnectedError) as err:
                self._is_connected = False
                raise ApiConnectionError(f"Connection error getting devices: {err}") from err
            except asyncio.TimeoutError as err:
                raise ApiTimeoutError(f"Timeout getting devices: {err}") from err
            except (ValueError, Exception) as err:
                raise ApiError(f"Error getting devices: {err}") from err

        return await self._execute_with_retry(_get_devices)

    async def get_device(self, device_id: int) -> Optional[Dict[str, Any]]:
        """Get a device by ID."""
        async def _get_device():
            try:
                response = await self._session.get(
                    f"{self._base_url}/devices/{device_id}",
                    headers={API_AUTH_KEY_HEADER: self._auth_key},
                    raise_for_status=True,
                    timeout=30,  # Add explicit timeout
                )
                data = await response.json()
                devices = data.get("devices", [])
                return devices[0] if devices else None
            except aiohttp.ClientResponseError as err:
                if err.status == 401:
                    self._auth_key = None
                    self._is_connected = False
                    raise ApiAuthError("Invalid auth key") from err
                if err.status == 404:
                    return None
                raise ApiError(f"Error getting device {device_id}: {err}") from err
            except (aiohttp.ClientConnectionError, aiohttp.ServerDisconnectedError) as err:
                self._is_connected = False
                raise ApiConnectionError(f"Connection error getting device {device_id}: {err}") from err
            except asyncio.TimeoutError as err:
                raise ApiTimeoutError(f"Timeout getting device {device_id}: {err}") from err
            except (ValueError, Exception) as err:
                raise ApiError(f"Error getting device {device_id}: {err}") from err

        return await self._execute_with_retry(_get_device)

    async def get_shades(self) -> List[ShadeState]:
        """Get all shades."""
        _LOGGER.debug("Fetching all shades")

        async def _get_shades():
            try:
                timeout = aiohttp.ClientTimeout(total=30)
                async with self._session.get(
                    f"{self._base_url}/shades",
                    headers=self._get_headers(),
                    timeout=timeout,
                ) as response:
                    if response.status == 200:
                        response_json = await response.json()
                        shades = []

                        if not isinstance(response_json, list):
                            _LOGGER.error("Unexpected response format: %s", response_json)
                            return []

                        for shade_data in response_json:
                            try:
                                shade = ShadeState.from_dict(shade_data)
                                shades.append(shade)
                            except (KeyError, ValueError) as err:
                                _LOGGER.warning("Error parsing shade data: %s", err)

                        _LOGGER.info("Successfully retrieved %s shades", len(shades))
                        return shades
                    elif response.status == 401:
                        _LOGGER.warning("Authentication error getting shades")
                        raise ApiAuthError("Invalid auth key")
                    else:
                        error_text = await response.text()
                        _LOGGER.error(
                            "Error getting shades: HTTP %s - %s",
                            response.status, error_text
                        )
                        raise ApiError(f"Error getting shades: {response.status}")
            except aiohttp.ClientResponseError as err:
                _LOGGER.error("Response error getting shades: %s", err)
                if err.status == 401:
                    raise ApiAuthError("Invalid auth key") from err
                raise ApiError(f"Error getting shades: {err}") from err
            except (aiohttp.ClientConnectionError, aiohttp.ServerDisconnectedError) as err:
                _LOGGER.error("Connection error getting shades: %s", err)
                raise ApiConnectionError(f"Connection error getting shades: {err}") from err
            except asyncio.TimeoutError as err:
                _LOGGER.error("Timeout getting shades: %s", err)
                raise ApiTimeoutError(f"Timeout getting shades: {err}") from err
            except Exception as err:
                _LOGGER.exception("Unexpected error getting shades: %s", err)
                raise ApiError(f"Error getting shades: {err}") from err

        return await self._execute_with_retry(_get_shades)

    async def get_shade(self, shade_id: int) -> Optional[ShadeState]:
        """Get a shade by ID."""
        async def _get_shade():
            try:
                response = await self._session.get(
                    f"{self._base_url}/shades/{shade_id}",
                    headers={API_AUTH_KEY_HEADER: self._auth_key},
                    raise_for_status=True,
                    timeout=30,  # Add explicit timeout
                )
                data = await response.json()
                shades = data.get("shades", [])
                return ShadeState.from_dict(shades[0]) if shades else None
            except aiohttp.ClientResponseError as err:
                if err.status == 401:
                    self._auth_key = None
                    self._is_connected = False
                    raise ApiAuthError("Invalid auth key") from err
                if err.status == 404:
                    return None
                raise ApiError(f"Error getting shade {shade_id}: {err}") from err
            except (aiohttp.ClientConnectionError, aiohttp.ServerDisconnectedError) as err:
                self._is_connected = False
                raise ApiConnectionError(f"Connection error getting shade {shade_id}: {err}") from err
            except asyncio.TimeoutError as err:
                raise ApiTimeoutError(f"Timeout getting shade {shade_id}: {err}") from err
            except (ValueError, Exception) as err:
                raise ApiError(f"Error getting shade {shade_id}: {err}") from err

        return await self._execute_with_retry(_get_shade)

    async def set_shades_state(self, shades: List[ShadeState]) -> bool:
        """Set shades state."""
        async def _set_shades_state():
            try:
                response = await self._session.post(
                    f"{self._base_url}/shades/setstate",
                    headers={
                        API_AUTH_KEY_HEADER: self._auth_key,
                        "Content-Type": "application/json",
                    },
                    json={"shades": [shade.to_dict() for shade in shades]},
                    raise_for_status=True,
                    timeout=30,  # Add explicit timeout
                )
                data = await response.json()
                return data.get("status") == "success"
            except aiohttp.ClientResponseError as err:
                if err.status == 401:
                    self._auth_key = None
                    self._is_connected = False
                    raise ApiAuthError("Invalid auth key") from err
                raise ApiError(f"Error setting shades state: {err}") from err
            except (aiohttp.ClientConnectionError, aiohttp.ServerDisconnectedError) as err:
                self._is_connected = False
                raise ApiConnectionError(f"Connection error setting shades state: {err}") from err
            except asyncio.TimeoutError as err:
                raise ApiTimeoutError(f"Timeout setting shades state: {err}") from err
            except (ValueError, Exception) as err:
                raise ApiError(f"Error setting shades state: {err}") from err

        return await self._execute_with_retry(_set_shades_state)

    async def set_position(self, shade_id: int, position: int) -> bool:
        """Set shade position."""
        _LOGGER.debug("Setting shade %s position to %s", shade_id, position)

        # Get the shade first to make sure it exists
        try:
            shade = await self.get_shade(shade_id)
            if not shade:
                _LOGGER.error("Shade %s not found", shade_id)
                return False
        except Exception as err:
            _LOGGER.error("Error checking shade %s: %s", shade_id, err)
            # Continue anyway, as the actual set position may still work

        async def _set_position():
            try:
                timeout = aiohttp.ClientTimeout(total=30)
                async with self._session.post(
                    f"{self._base_url}/shades/{shade_id}/position",
                    headers=self._get_headers(),
                    json={"position": position},
                    timeout=timeout,
                ) as response:
                    if response.status == 200:
                        _LOGGER.info("Successfully set position for shade %s to %s",
                                     shade_id, position)
                        return True
                    elif response.status == 401:
                        _LOGGER.warning(
                            "Authentication error setting position for shade %s", shade_id
                        )
                        raise ApiAuthError("Invalid auth key")
                    elif response.status == 404:
                        _LOGGER.error("Shade %s not found", shade_id)
                        return False
                    else:
                        error_text = await response.text()
                        _LOGGER.error(
                            "Error setting position for shade %s: HTTP %s - %s",
                            shade_id, response.status, error_text
                        )
                        return False
            except aiohttp.ClientResponseError as err:
                _LOGGER.error("Response error setting position for shade %s: %s", shade_id, err)
                if err.status == 401:
                    raise ApiAuthError("Invalid auth key") from err
                raise ApiError(f"Error setting position: {err}") from err
            except (aiohttp.ClientConnectionError, aiohttp.ServerDisconnectedError) as err:
                _LOGGER.error("Connection error setting position for shade %s: %s", shade_id, err)
                raise ApiConnectionError(f"Connection error setting position: {err}") from err
            except asyncio.TimeoutError as err:
                _LOGGER.error("Timeout setting position for shade %s: %s", shade_id, err)
                raise ApiTimeoutError(f"Timeout setting position: {err}") from err
            except Exception as err:
                _LOGGER.exception("Unexpected error setting position for shade %s: %s", shade_id, err)
                raise ApiError(f"Error setting position: {err}") from err

        try:
            return await self._execute_with_retry(_set_position)
        except Exception as err:
            _LOGGER.error("Failed to set position for shade %s: %s", shade_id, err)
            return False

    async def open_shade(self, shade_id: int) -> bool:
        """Open a shade."""
        try:
            return await self.set_position(shade_id, OPEN_VALUE)
        except Exception as err:
            _LOGGER.error("Error opening shade %s: %s", shade_id, err)
            raise

    async def close_shade(self, shade_id: int) -> bool:
        """Close a shade."""
        try:
            return await self.set_position(shade_id, CLOSED_VALUE)
        except Exception as err:
            _LOGGER.error("Error closing shade %s: %s", shade_id, err)
            raise

    async def stop_shade(self, shade_id: int) -> bool:
        """Stop a shade."""
        async def _stop_shade():
            try:
                response = await self._session.post(
                    f"{self._base_url}/shades/{shade_id}/stop",
                    headers={API_AUTH_KEY_HEADER: self._auth_key},
                    raise_for_status=True,
                    timeout=30,  # Add explicit timeout
                )
                return True
            except aiohttp.ClientResponseError as err:
                if err.status == 401:
                    self._auth_key = None
                    self._is_connected = False
                    raise ApiAuthError("Invalid auth key") from err
                raise ApiError(f"Error stopping shade {shade_id}: {err}") from err
            except (aiohttp.ClientConnectionError, aiohttp.ServerDisconnectedError) as err:
                self._is_connected = False
                raise ApiConnectionError(f"Connection error stopping shade {shade_id}: {err}") from err
            except asyncio.TimeoutError as err:
                raise ApiTimeoutError(f"Timeout stopping shade {shade_id}: {err}") from err
            except (ValueError, Exception) as err:
                raise ApiError(f"Error stopping shade {shade_id}: {err}") from err

        try:
            return await self._execute_with_retry(_stop_shade)
        except Exception as err:
            _LOGGER.error("Error stopping shade %s: %s", shade_id, err)
            raise

    def has_shade(self, shade_id: int) -> bool:
        """Check if a shade exists."""
        return shade_id in self.shades

    def _is_auth_valid(self) -> bool:
        """Check if the current auth key is valid."""
        return self._auth_key and time.time() < self._auth_expiry

    def _get_headers(self):
        """Get headers for API requests."""
        return {
            API_AUTH_TOKEN_HEADER: self._auth_token,
            API_AUTH_KEY_HEADER: self._auth_key,
        }