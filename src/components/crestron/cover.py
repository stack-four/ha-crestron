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

    # @property
    # def is_open(self):
    #     return self._shade.isOpen()

#TODO Add support for isOpening + isClosing ()
    # @property
    # def is_opening(self):
    #     return self._shade.is_opening()

    # @property
    # def is_closing(self):
    #     return self._shade.is_closing()

    async def async_is_opening(self):
        return self._shade.isOpening()

    async def async_is_open(self):
        return self._shade.isClosed()

    async def async_is_closed(self):
        return self._shade.isClosed()

    async def async_is_closing(self):
        return self._shade.isClosing()
    
    async def async_set_cover_position(self, **kwargs)->None:
        self._shade.setPosition(kwargs["position"])

    async def async_open_cover(self)->None:
        self._shade.open()

    async def async_close_cover(self)->None:
        self._shade.close()

    # @callback
    # async def async_update_group_state(self) -> None:
        # """Query all members and determine the light group state."""
        # states = [
        #     state
        #     for entity_id in self._entity_ids
        #     if (state := self.hass.states.get(entity_id)) is not None
        # ]
        # on_states = [state for state in states if state.state == STATE_ON]

        # valid_state = self.mode(
        #     state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE) for state in states
        # )

        # if not valid_state:
        #     # Set as unknown if any / all member is unknown or unavailable
        #     self._attr_is_on = None
        # else:
        #     # Set as ON if any / all member is ON
        #     self._attr_is_on = self.mode(state.state == STATE_ON for state in states)

        # self._attr_available = any(state.state != STATE_UNAVAILABLE for state in states)
        # self._attr_brightness = reduce_attribute(on_states, ATTR_BRIGHTNESS)

        # self._attr_hs_color = reduce_attribute(
        #     on_states, ATTR_HS_COLOR, reduce=mean_tuple
        # )
        # self._attr_rgb_color = reduce_attribute(
        #     on_states, ATTR_RGB_COLOR, reduce=mean_tuple
        # )
        # self._attr_rgbw_color = reduce_attribute(
        #     on_states, ATTR_RGBW_COLOR, reduce=mean_tuple
        # )
        # self._attr_rgbww_color = reduce_attribute(
        #     on_states, ATTR_RGBWW_COLOR, reduce=mean_tuple
        # )
        # self._attr_xy_color = reduce_attribute(
        #     on_states, ATTR_XY_COLOR, reduce=mean_tuple
        # )

        # self._attr_color_temp_kelvin = reduce_attribute(
        #     on_states, ATTR_COLOR_TEMP_KELVIN
        # )
        # self._attr_min_color_temp_kelvin = reduce_attribute(
        #     states, ATTR_MIN_COLOR_TEMP_KELVIN, default=2000, reduce=min
        # )
        # self._attr_max_color_temp_kelvin = reduce_attribute(
        #     states, ATTR_MAX_COLOR_TEMP_KELVIN, default=6500, reduce=max
        # )

        # self._attr_effect_list = None
        # all_effect_lists = list(find_state_attributes(states, ATTR_EFFECT_LIST))
        # if all_effect_lists:
        #     # Merge all effects from all effect_lists with a union merge.
        #     self._attr_effect_list = list(set().union(*all_effect_lists))
        #     self._attr_effect_list.sort()
        #     if "None" in self._attr_effect_list:
        #         self._attr_effect_list.remove("None")
        #         self._attr_effect_list.insert(0, "None")

        # self._attr_effect = None
        # all_effects = list(find_state_attributes(on_states, ATTR_EFFECT))
        # if all_effects:
        #     # Report the most common effect.
        #     effects_count = Counter(itertools.chain(all_effects))
        #     self._attr_effect = effects_count.most_common(1)[0][0]

        # supported_color_modes = {ColorMode.ONOFF}
        # all_supported_color_modes = list(
        #     find_state_attributes(states, ATTR_SUPPORTED_COLOR_MODES)
        # )
        # if all_supported_color_modes:
        #     # Merge all color modes.
        #     supported_color_modes = filter_supported_color_modes(
        #         cast(set[ColorMode], set().union(*all_supported_color_modes))
        #     )
        # self._attr_supported_color_modes = supported_color_modes

        # self._attr_color_mode = ColorMode.UNKNOWN
        # all_color_modes = list(find_state_attributes(on_states, ATTR_COLOR_MODE))
        # if all_color_modes:
        #     # Report the most common color mode, select brightness and onoff last
        #     color_mode_count = Counter(itertools.chain(all_color_modes))
        #     if ColorMode.ONOFF in color_mode_count:
        #         if ColorMode.ONOFF in supported_color_modes:
        #             color_mode_count[ColorMode.ONOFF] = -1
        #         else:
        #             color_mode_count.pop(ColorMode.ONOFF)
        #     if ColorMode.BRIGHTNESS in color_mode_count:
        #         if ColorMode.BRIGHTNESS in supported_color_modes:
        #             color_mode_count[ColorMode.BRIGHTNESS] = 0
        #         else:
        #             color_mode_count.pop(ColorMode.BRIGHTNESS)
        #     if color_mode_count:
        #         self._attr_color_mode = color_mode_count.most_common(1)[0][0]
        #     else:
        #         self._attr_color_mode = next(iter(supported_color_modes))

        # self._attr_supported_features = LightEntityFeature(0)
        # for support in find_state_attributes(states, ATTR_SUPPORTED_FEATURES):
        #     # Merge supported features by emulating support for every feature
        #     # we find.
        #     self._attr_supported_features |= support
        # # Bitwise-and the supported features with the GroupedLight's features
        # # so that we don't break in the future when a new feature is added.
        # self._attr_supported_features &= SUPPORT_GROUP_LIGHT
    
    # async def async_close_cover(self, **kwargs: Any) -> None:
    #     """Move the covers down."""
    #     data = {ATTR_ENTITY_ID: self._covers[KEY_OPEN_CLOSE]}
    #     await self.hass.services.async_call(
    #         DOMAIN, SERVICE_CLOSE_COVER, data, blocking=True, context=self._context
    #     )


    # async def async_stop_cover(self, **kwargs: Any) -> None:
    #     """Fire the stop action."""
    #     data = {ATTR_ENTITY_ID: self._covers[KEY_STOP]}
    #     await self.hass.services.async_call(
    #         DOMAIN, SERVICE_STOP_COVER, data, blocking=True, context=self._context
    #     )

    # async def async_stop_cover(self, **kwargs):
    #     self._shade.set_digital(self._stop_join, 1)
    #     call_later(self.hass, 0.2, self._shade.set_digital(self._stop_join, 0))
