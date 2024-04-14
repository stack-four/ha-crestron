"""Platform for Crestron Shades integration."""

from datetime import timedelta
import logging

import async_timeout

from crestron import CrestronShade, CrestronHub, ShadeState

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from homeassistant.helpers.event import call_later
from homeassistant.components.cover import (
    CoverEntity,
    DEVICE_CLASS_SHADE,
    CoverDeviceClass,
    CoverEntityFeature,
    ATTR_POSITION,
    STATE_OPENING,
    STATE_OPEN,
    STATE_CLOSING,
    STATE_CLOSED,
)

from homeassistant.const import CONF_NAME, CONF_TYPE
from .const import (
    HUB,
    DOMAIN,
    CONF_IS_OPENING_JOIN,
    CONF_IS_CLOSING_JOIN,
    CONF_IS_CLOSED_JOIN,
    CONF_STOP_JOIN,
    CONF_POS_JOIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_TYPE): cv.string,
        vol.Required(CONF_POS_JOIN): cv.positive_int,
        vol.Required(CONF_IS_OPENING_JOIN): cv.positive_int,
        vol.Required(CONF_IS_CLOSING_JOIN): cv.positive_int,
        vol.Required(CONF_IS_CLOSED_JOIN): cv.positive_int,
        vol.Required(CONF_STOP_JOIN): cv.positive_int,
    },
    extra=vol.ALLOW_EXTRA,
)


# async def async_setup_entry(hass, entry, async_add_entities):
#     # assuming API object stored here by __init__.py
#     hub = hass.data[DOMAIN][entry.entry_id]
#     coordinator = MyCoordinator(hass, hub)

#     # Fetch initial data so we have data when entities subscribe
#     #
#     # If the refresh fails, async_config_entry_first_refresh will
#     # raise ConfigEntryNotReady and setup will try again later
#     #
#     # If you do not want to retry setup on failure, use
#     # coordinator.async_refresh() instead
#     #
#     await coordinator.async_config_entry_first_refresh()

#     async_add_entities(
#         MyEntity(coordinator, idx) for idx, ent in enumerate(coordinator.data)
#     )


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    hub: CrestronHub = hass.data[DOMAIN][HUB]
    # TODO Use config to help determine which entities to add?
    shades = await hub.getShades()
    _LOGGER.info(f"Found {shades.count} shades on Hub")
    async_add_entities(list(map(lambda s: CrestronShadeEntity(s, config), shades)))


class CrestronShadesCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass, my_api):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Crestron Shade",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
        )
        self.my_api = my_api

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                # Grab active context variables to limit data required to be fetched from API
                # Note: using context is not required if there is no need or ability to limit
                # data retrieved from API.
                listening_idx = set(self.async_contexts())
                return await self.my_api.fetch_data(listening_idx)
        except ApiAuthError as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise ConfigEntryAuthFailed from err
        except ApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")


class MyEntity(CoordinatorEntity[CrestronShadesCoordinator], LightEntity):
    """An entity using CoordinatorEntity.

    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass
      available

    """

    def __init__(self, coordinator, idx):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, context=idx)
        self.idx = idx

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.coordinator.data[self.idx]["state"]
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the light on.

        Example method how to request data updates.
        """
        # Do the turning on.
        # ...

        # Update the data
        await self.coordinator.async_request_refresh()


class CrestronShadeEntity(CoordinatorEntity[CrestronShadesCoordinator], CoverEntity):
    _attr_available: bool
    _attr_device_class = CoverDeviceClass.Shade
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(
        self, coordinator: CrestronShadesCoordinator, initialState: ShadeState, config
    ):
        self._name = config.get(CONF_NAME)
        self._attr_current_cover_position
        self._attr_unique_id = f"{coordinator.unique_id}-{initialState.id}"
        self._attr_device_info = coordinator.device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        if not self._attr_available:
            return True

        if active_accessory := self.coordinator.get_coil_value(
            self._coil_active_accessory
        ):
            return active_accessory == "ON"

        return False

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        await self.coordinator.async_write_coil(self._coil_temporary_lux, lux)

    async def async_added_to_hass(self):
        self._shade.register_callback(self.process_callback)

    async def async_will_remove_from_hass(self):
        self._shade.remove_callback(self.process_callback)

    async def process_callback(self, cbtype, value):
        self.async_write_ha_state()

    async def isAvailable(self):
        return await self._shade._hub.getVersion() is not None

    async def async_update(self):
        """Retrieve latest state."""
        self._state = await self._shade.__getState()

    @property
    def name(self):
        return self._name

    @property
    def device_class(self):
        return self._attr_device_class

    @property
    def supported_features(self):
        return self._supported_features

    @property
    def should_poll(self):
        return self._should_poll

    @property
    def current_cover_position(self) -> int:
        """Return the current position of the cover."""
        return self._state.position

    @property
    def current_cover_percentage_open(self) -> float:
        """Return the current position of the cover."""
        return round(self._state.position / self._shade.SHADE_OPEN_POSITION, 3)

    @property
    def is_closed(self):
        return self._state.position == self._shade.SHADE_CLOSED_POSITION

    @property
    def is_open(self):
        return self._state.position == self._shade.SHADE_OPEN_POSITION

    @property
    def is_closing(self):
        return self._shade.is_closing()

    @property
    def is_closed(self):
        return self._shade.is_closed()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position: int = kwargs["position"]
        self._set_position = round(position, -1)
        if self._position == position:
            return

        self._listen_cover()
        self._requested_closing = (
            self._position is not None and position < self._position
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._switch.control(True)
        await self.coordinator.async_request_refresh()

    async def async_update(self) -> None:
        """Update status of cover."""
        try:
            await self._shade.__getState(True)
            self._attr_available = True

        except (session_manager.ConnectionError, session_manager.InvalidPasswordError):
            self._attr_available = False

    async def async_is_opening(self):
        return self._shade.is_opening()

    async def async_set_cover_position(self, **kwargs):
        self._shade.set_analog(self._pos_join, int(kwargs["position"]) * 655)

    async def async_open_cover(self):
        return self._shade.open()

    async def async_close_cover(self):
        return self._shade.close()

    async def async_stop_cover(self, **kwargs):
        self._shade.set_digital(self._stop_join, 1)
        call_later(self.hass, 0.2, self._shade.set_digital(self._stop_join, 0))
