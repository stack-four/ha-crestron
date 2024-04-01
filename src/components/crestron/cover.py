"""Platform for Crestron Shades integration."""

import logging
from crestron import CrestronShade, CrestronHub

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import call_later
from homeassistant.components.cover import (
    CoverEntity,
    DEVICE_CLASS_SHADE,
    SUPPORT_OPEN,
    SUPPORT_CLOSE,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
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


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    hub: CrestronHub = hass.data[DOMAIN][HUB]
    # TODO Use config to help determine which entities to add?
    shades = await hub.getShades()
    _LOGGER.info(f"Found {shades.count} shades on Hub")
    async_add_entities(list(map(lambda s: CrestronShadeEntity(s, config), shades)))


class CrestronShadeEntity(CoverEntity):

    def __init__(self, shade: CrestronShade, config):
        self._shade = shade
        self._device_class = DEVICE_CLASS_SHADE
        self._supported_features = (
            SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION | SUPPORT_STOP
        )
        self._should_poll = False

        self._name = config.get(CONF_NAME)
        self._is_opening_join = config.get(CONF_IS_OPENING_JOIN)
        self._is_closing_join = config.get(CONF_IS_CLOSING_JOIN)
        self._is_closed_join = config.get(CONF_IS_CLOSED_JOIN)
        self._stop_join = config.get(CONF_STOP_JOIN)
        self._pos_join = config.get(CONF_POS_JOIN)

    async def async_added_to_hass(self):
        self._shade.register_callback(self.process_callback)

    async def async_will_remove_from_hass(self):
        self._shade.remove_callback(self.process_callback)

    async def process_callback(self, cbtype, value):
        self.async_write_ha_state()

    async def isAvailable(self):
        return await self._shade._hub.getVersion() is not None

    @property
    def name(self):
        return self._name

    @property
    def device_class(self):
        return self._device_class

    @property
    def supported_features(self):
        return self._supported_features

    @property
    def should_poll(self):
        return self._should_poll

    @property
    def current_cover_position(self):
        return self._shade.getPositionAsPercentage()

    @property
    def is_open(self):
        return self._shade.is_open()

    @property
    def is_opening(self):
        return self._shade.is_opening()

    @property
    def is_closing(self):
        return self._shade.is_closing()

    @property
    def is_closed(self):
        return self._shade.is_closed()

    async def async_set_cover_position(self, **kwargs):
        self._shade.set_analog(self._pos_join, int(kwargs["position"]) * 655)

    async def async_open_cover(self):
        return self._shade.open()

    async def async_close_cover(self):
        return self._shade.close()

    async def async_stop_cover(self, **kwargs):
        self._shade.set_digital(self._stop_join, 1)
        call_later(self.hass, 0.2, self._shade.set_digital(self._stop_join, 0))
