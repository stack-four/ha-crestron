"""Crestron API client."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, cast
import aiohttp
import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api_errors import ApiAuthError, ApiConnectionError, ApiError, ApiTimeoutError

_LOGGER = logging.getLogger(__name__)

API_AUTH_TOKEN_HEADER = "Crestron-RestAPI-AuthToken"
API_AUTH_KEY_HEADER = "Crestron-RestAPI-AuthKey"

OPEN_VALUE = 65535
CLOSED_VALUE = 0


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

    @property
    def host(self) -> str:
        """Return host."""
        return self._host

    @property
    def auth_token(self) -> str:
        """Return auth token."""
        return self._auth_token

    async def login(self) -> bool:
        """Login and get auth key."""
        if self._auth_key:
            return True

        try:
            response = await self._session.get(
                f"{self._base_url}/login",
                headers={API_AUTH_TOKEN_HEADER: self._auth_token},
                raise_for_status=True,
            )
            data = await response.json()
            self._auth_key = data.get("authkey")
            if not self._auth_key:
                raise ApiAuthError("No auth key received from API")
            self._is_connected = True
            return True
        except aiohttp.ClientResponseError as err:
            if err.status == 401:
                raise ApiAuthError("Invalid auth token") from err
            raise ApiError(f"Error logging in: {err}") from err
        except aiohttp.ClientError as err:
            raise ApiConnectionError(f"Error connecting to API: {err}") from err
        except asyncio.TimeoutError as err:
            raise ApiTimeoutError(f"Timeout connecting to API: {err}") from err
        except (ValueError, Exception) as err:
            raise ApiError(f"Error connecting to API: {err}") from err

    async def ping(self) -> bool:
        """Ping the API."""
        try:
            await self._session.get(
                self._base_url,
                headers={API_AUTH_TOKEN_HEADER: self._auth_token},
                raise_for_status=True,
            )
            return True
        except aiohttp.ClientResponseError as err:
            if err.status == 401:
                raise ApiAuthError("Invalid auth token") from err
            raise ApiError(f"Error pinging API: {err}") from err
        except aiohttp.ClientError as err:
            raise ApiConnectionError(f"Error connecting to API: {err}") from err
        except asyncio.TimeoutError as err:
            raise ApiTimeoutError(f"Timeout connecting to API: {err}") from err
        except (ValueError, Exception) as err:
            raise ApiError(f"Error connecting to API: {err}") from err

    async def get_devices(self) -> List[Dict[str, Any]]:
        """Get all devices."""
        await self.login()
        try:
            response = await self._session.get(
                f"{self._base_url}/devices",
                headers={API_AUTH_KEY_HEADER: self._auth_key},
                raise_for_status=True,
            )
            data = await response.json()
            return data.get("devices", [])
        except aiohttp.ClientResponseError as err:
            if err.status == 401:
                self._auth_key = None
                raise ApiAuthError("Invalid auth key") from err
            raise ApiError(f"Error getting devices: {err}") from err
        except aiohttp.ClientError as err:
            raise ApiConnectionError(f"Error connecting to API: {err}") from err
        except asyncio.TimeoutError as err:
            raise ApiTimeoutError(f"Timeout connecting to API: {err}") from err
        except (ValueError, Exception) as err:
            raise ApiError(f"Error connecting to API: {err}") from err

    async def get_device(self, device_id: int) -> Optional[Dict[str, Any]]:
        """Get a device by ID."""
        await self.login()
        try:
            response = await self._session.get(
                f"{self._base_url}/devices/{device_id}",
                headers={API_AUTH_KEY_HEADER: self._auth_key},
                raise_for_status=True,
            )
            data = await response.json()
            devices = data.get("devices", [])
            return devices[0] if devices else None
        except aiohttp.ClientResponseError as err:
            if err.status == 401:
                self._auth_key = None
                raise ApiAuthError("Invalid auth key") from err
            if err.status == 404:
                return None
            raise ApiError(f"Error getting device {device_id}: {err}") from err
        except aiohttp.ClientError as err:
            raise ApiConnectionError(f"Error connecting to API: {err}") from err
        except asyncio.TimeoutError as err:
            raise ApiTimeoutError(f"Timeout connecting to API: {err}") from err
        except (ValueError, Exception) as err:
            raise ApiError(f"Error connecting to API: {err}") from err

    async def get_shades(self) -> List[ShadeState]:
        """Get all shades."""
        await self.login()
        try:
            response = await self._session.get(
                f"{self._base_url}/shades",
                headers={API_AUTH_KEY_HEADER: self._auth_key},
                raise_for_status=True,
            )
            data = await response.json()
            shades = data.get("shades", [])
            self.shades = {shade["id"]: shade for shade in shades}
            return [ShadeState.from_dict(shade) for shade in shades]
        except aiohttp.ClientResponseError as err:
            if err.status == 401:
                self._auth_key = None
                raise ApiAuthError("Invalid auth key") from err
            raise ApiError(f"Error getting shades: {err}") from err
        except aiohttp.ClientError as err:
            raise ApiConnectionError(f"Error connecting to API: {err}") from err
        except asyncio.TimeoutError as err:
            raise ApiTimeoutError(f"Timeout connecting to API: {err}") from err
        except (ValueError, Exception) as err:
            raise ApiError(f"Error connecting to API: {err}") from err

    async def get_shade(self, shade_id: int) -> Optional[ShadeState]:
        """Get a shade by ID."""
        await self.login()
        try:
            response = await self._session.get(
                f"{self._base_url}/shades/{shade_id}",
                headers={API_AUTH_KEY_HEADER: self._auth_key},
                raise_for_status=True,
            )
            data = await response.json()
            shades = data.get("shades", [])
            return ShadeState.from_dict(shades[0]) if shades else None
        except aiohttp.ClientResponseError as err:
            if err.status == 401:
                self._auth_key = None
                raise ApiAuthError("Invalid auth key") from err
            if err.status == 404:
                return None
            raise ApiError(f"Error getting shade {shade_id}: {err}") from err
        except aiohttp.ClientError as err:
            raise ApiConnectionError(f"Error connecting to API: {err}") from err
        except asyncio.TimeoutError as err:
            raise ApiTimeoutError(f"Timeout connecting to API: {err}") from err
        except (ValueError, Exception) as err:
            raise ApiError(f"Error connecting to API: {err}") from err

    async def set_shades_state(self, shades: List[ShadeState]) -> bool:
        """Set shades state."""
        await self.login()
        try:
            response = await self._session.post(
                f"{self._base_url}/shades/setstate",
                headers={
                    API_AUTH_KEY_HEADER: self._auth_key,
                    "Content-Type": "application/json",
                },
                json={"shades": [shade.to_dict() for shade in shades]},
                raise_for_status=True,
            )
            data = await response.json()
            return data.get("status") == "success"
        except aiohttp.ClientResponseError as err:
            if err.status == 401:
                self._auth_key = None
                raise ApiAuthError("Invalid auth key") from err
            raise ApiError(f"Error setting shades state: {err}") from err
        except aiohttp.ClientError as err:
            raise ApiConnectionError(f"Error connecting to API: {err}") from err
        except asyncio.TimeoutError as err:
            raise ApiTimeoutError(f"Timeout connecting to API: {err}") from err
        except (ValueError, Exception) as err:
            raise ApiError(f"Error connecting to API: {err}") from err

    async def open_shade(self, shade_id: int, shade_name: str = "", room_id: int = 0) -> bool:
        """Open a shade."""
        shade = ShadeState(
            position=OPEN_VALUE,
            id=shade_id,
            name=shade_name,
            roomId=room_id,
        )
        return await self.set_shades_state([shade])

    async def close_shade(self, shade_id: int, shade_name: str = "", room_id: int = 0) -> bool:
        """Close a shade."""
        shade = ShadeState(
            position=CLOSED_VALUE,
            id=shade_id,
            name=shade_name,
            roomId=room_id,
        )
        return await self.set_shades_state([shade])

    async def set_shade_position(
        self, shade_id: int, position: int, shade_name: str = "", room_id: int = 0
    ) -> bool:
        """Set shade position."""
        shade = ShadeState(
            position=position,
            id=shade_id,
            name=shade_name,
            roomId=room_id,
        )
        return await self.set_shades_state([shade])

    def has_shade(self, shade_id: int) -> bool:
        """Check if a shade exists."""
        return shade_id in self.shades