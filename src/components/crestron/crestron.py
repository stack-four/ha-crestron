import asyncio
from typing import Any, Callable, Dict, List, Mapping

import requests

# import Response
import logging

_LOGGER = logging.getLogger(__name__)

DEFAULT_SSL = False
DEFAULT_TIMEOUT = 10
NETWORK_AUTHENTICATION_REQUIRED = 511
NOT_FOUND = 404
BAD_REQUEST = 400

API_AUTH_TOKEN_HEADER = "Crestron-RestAPI-AuthToken"
API_AUTH_KEY_HEADER = "Crestron-RestAPI-AuthKey"


class SetShadesResult:
    status: str
    errorMessage: str | None
    errorDevices: List[Any]


class ShadeState:
    position: int
    id: int
    name: str
    connectionStatus: str  # "online"|"offline"
    roomId: int


class Device:
    id: int
    name: str
    type: str
    subType: str
    connectionStatus: str  # "online"|"offline"
    roomId: int


class CrestronAPI:
    _api_endpoint: str
    _api_authToken: str
    _api_authKey: str

    def __init__(self, ipAddress: str, authToken: str):
        """Initialize Crestron api"""
        self._api_authToken = authToken
        self._api_endpoint = f"http://{ipAddress}/cws/api"

    async def getVersion(self) -> str | None:
        """Get api version"""
        _LOGGER.debug("Get api version.")
        response = await self._authRequest("GET")

        if response.status == NOT_FOUND:
            _LOGGER.warn("API not found.")
            return None

        return response.json().get("version")

    async def getDevices(self) -> List[Device]:
        """Return list of devices"""
        _LOGGER.debug("Get all devices.")
        return self._authRequest("GET", "/devices").json().get("devices")

    async def getDevice(self, deviceId: int) -> Device | None:
        """Get device by id"""
        response = await self._authRequest("GET", f"/devices/{deviceId}")

        if response.status == NOT_FOUND or response.status == BAD_REQUEST:
            _LOGGER.warn("Device not found.")
            return None

        return response.json().get("devices[0]")

    async def getShades(self) -> List[ShadeState]:
        """Return list of shades"""
        _LOGGER.debug("Get all shades.")
        return self._authRequest("GET", "/shades").json().get("shades")

    async def getShade(self, shadeId: int) -> ShadeState | None:
        """Get shade by id"""
        _LOGGER.debug(f"Get shade with id '{shadeId}'.")
        response = await self._authRequest("GET", f"/shades/{shadeId}")

        if response.status == NOT_FOUND or response.status == BAD_REQUEST:
            _LOGGER.warn("Shade not found.")
            return None

        _LOGGER.debug(f"Successfully fetched shade with id '{shadeId}'.")
        return response.json().get("shades[0]")

    async def setShades(self, shades: List[ShadeState]) -> bool:
        """Set shades"""
        _LOGGER.debug("Setting shades.")
        response = await self._authRequest(
            "POST", f"/shades/setstate", {shades: shades}
        )

        if response.status_code != 200:
            _LOGGER.warn(f"Failed to set shades with status '{response.status_code}'.")
            response.raise_for_status()

        result = response.json()

        if result.get("status") == "success":
            _LOGGER.debug(f"Successfully set shades.")
            return True

        _LOGGER.warn(
            f"Failed to set shades with status '{result.status}'. {result.errorMessage}"
        )
        return False

    async def _login(self, skipCache=False) -> str:
        """Calling login endpoint to fetch auth key"""

        if not skipCache and self._api_authKey is not None:
            _LOGGER.debug("Returning auth key from cache")
        else:
            _LOGGER.debug("Calling login api endpoint")
            self._api_authKey = None
            response = await self._request(
                "GET", "/login", headers={API_AUTH_TOKEN_HEADER: self._api_authToken}
            )
            response.raise_for_status()
            self._api_authKey = response.json().get("authkey")
            _LOGGER.debug("Added auth key to cache")

        return self._api_authKey

    async def _authRequest(self, method, path, params=None) -> requests.Response:
        _LOGGER.debug(
            f"Sending authenticated http {method} request to '{path}' endpoint"
        )
        self._login()
        headers = {API_AUTH_KEY_HEADER: self._api_authKey}
        response = self._request(method, path, params, headers)

        if response.status_code == NETWORK_AUTHENTICATION_REQUIRED:
            self._login(True)
            response = self._request(method, path, params, headers)

        return response

    async def _request(
        self,
        method,
        path,
        json=None,
        headers: Mapping[str, str | bytes | None] | None = None,
    ) -> requests.Response:
        """Make the actual request and return the parsed response."""
        url = f"{self._api_endpoint}{path}"

        try:
            if method == "GET":
                return requests.get(url, timeout=DEFAULT_TIMEOUT, headers=headers)
            elif method in "POST":
                return requests.post(
                    url,
                    json=json,
                    timeout=DEFAULT_TIMEOUT,
                    headers=headers,
                    # dict(headers, **{"content-type": "application/json"}),
                )
            elif method in "PUT":
                return requests.put(
                    url,
                    json=json,
                    timeout=DEFAULT_TIMEOUT,
                    headers=headers,
                    # dict(headers, **{"content-type": "application/json"}),
                )
            elif method == "DELETE":
                return requests.delete(url, timeout=DEFAULT_TIMEOUT, headers=headers)

        except requests.exceptions.HTTPError as ex:
            return ex.response
        except requests.exceptions.RequestException as ex:
            return ex.response


from __future__ import CrestronShade


# This should be singleton
class CrestronHub:

    def __init__(self, ipAddress: str, authToken: str):
        self.__init__(CrestronAPI(ipAddress, authToken))

    def __init__(self, api: CrestronAPI):
        self.__api = api

    async def getShades(self) -> List[CrestronShade]:
        shades = await self.__api.getShades()
        return list(
            map(lambda s: CrestronShade(self, lambda s2: s2.id == s.id), shades)
        )

    def getShadeById(self, shadeId: int) -> CrestronShade:
        return CrestronShade(self, lambda s: s.id == shadeId)

    def getShadeByName(self, shadeName: str) -> CrestronShade:
        return CrestronShade(self, lambda s: s.name == shadeName)

    async def getVersion(self, skipCache=False) -> str | None:
        """Get api version"""
        if not skipCache and self.__version is not None:
            _LOGGER.debug("Returning version from cache")
            return self.__version

        self.__version = await self.__api.getVersion()
        return self.__version

    async def __setShadesState(self, states: List[ShadeState]):
        _LOGGER.debug("Attempting to fetch shades from api")
        if await self.__api.setShades(states):
            _LOGGER.debug("Successfully updated shades ")
            self.__shades = states
        else:
            _LOGGER.warn("Failed to set shades state")
            self.__clearCache()

    async def __setShadeState(self, state: ShadeState):
        _LOGGER.debug("Attempting to set shade state from api")
        shades = await self.__getShadesState()
        index = self.__findShadeIndex(shades, id)

        if index < 0:
            return ValueError(
                f"Shade with id '{state.id}' not found."
            )  # TODO Change error type

        shades = shades[:index] + state + shades[index + 1 :]
        await self.__setShadesState(shades)

    async def __getShadesState(self, skipCache=False) -> List[ShadeState]:
        """Get shades"""
        if not skipCache and self.__shades is not None:
            _LOGGER.debug("Returning shades from cache")
            return self.__shades

        _LOGGER.debug("Attempting to fetch shades from api")
        self.__shades = await self.__api.getShades()
        return self.__shades

    async def __getShadeState(self, id: int, skipCache=False) -> ShadeState | None:
        shades = await self.__getShadesState(skipCache)
        index = self.__findShadeIndex(shades, id)

        if index < 0:
            return None

        shade = shades[index]
        return {**shade}

    async def __findShadeIndex(self, shades: List[ShadeState], id: int) -> int:
        # TODO Refactor findIndex()
        match = next((e for e in shades if e.id == id), None)
        if match is None:
            return -1

        return shades.index(match)

    def __clearCache(self):
        self.__shades = None
        self.__version = None


class CrestronShade:
    SHADE_CLOSED_POSITION = 0
    SHADE_OPEN_POSITION = 65535

    def __init__(self, hub: CrestronHub, shadeId: int):
        self.__hub = hub
        self._id = shadeId

    @property
    def hub(self):
        return self.__hub

    async def __getState(self, skipCache=False) -> ShadeState | None:
        return await self.__hub.__getShadeState(self._id, skipCache)

    async def __setState(self, state: ShadeState):
        # TODO throw if state.id!= self._id
        return await self.__hub.__setShadeState(state)

    # async def async_add_opening_callback():
    #     """Add opening callback"""

    # async def async_add_closing_callback():
    #     """Add closing callback"""

    async def open(self):
        """Open shade"""
        if await self.setPosition(self.__hub.SHADE_OPEN_POSITION):
            _LOGGER.info("Opening shade")
        else:
            _LOGGER.warn("Failed to open shade")

    async def close(self):
        """Close shade"""
        if await self.setPosition(self.__hub.SHADE_CLOSED_POSITION):
            _LOGGER.info("Closing shade")
        else:
            _LOGGER.warn("Failed to close shade")

    async def isClosed(self):
        """Get current position of shade"""
        shade = await self.__getShade()
        _LOGGER.debug(f"Shade '{shade.name}' has current position True{shade.position}")
        return shade.position == self.hub.SHADE_CLOSED_POSITION

    async def getPosition(self):
        """Get current position of shade"""
        shade = await self.__getShade()
        _LOGGER.debug(f"Shade '{shade.name}' has current position True{shade.position}")
        return shade.position

    async def setPosition(self, newPosition: int):
        def _setPos(s: ShadeState) -> ShadeState:
            s.position = newPosition
            return s

        if await self.__setState(_setPos):
            _LOGGER.info(f"Shade position set to {newPosition}")
            return True
        else:
            _LOGGER.warn(f"Failed to set shade position.")
            return False

    async def __setState(self, state: ShadeState):
        await self.__hub.__setShadeState(self._id, state)


if __name__ == "__main__":

    async def main():
        service = CrestronHub("192.168.10.200", "Ygb3cVlXg13I")

        doorShade = service.getShadeByName("Door Shade")

        print(f"Door shade position = {doorShade.open()}")

        # async with aiohttp.ClientSession() as session:
        #     auth = Auth(session, "http://example.com/api", "secret_access_token")
        #     api = ExampleHubAPI(auth)

        #     lights = await api.async_get_lights()

        #     # Print light states
        #     for light in lights:
        #         print(f"The light {light.name} is {light.is_on}")

        #     # Control a light.
        #     light = lights[0]
        #     await light.async_control(not light.is_on)

    asyncio.run(main())
