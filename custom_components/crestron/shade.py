"""Support for Crestron shades."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional, cast

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityDescription,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import CLOSED_VALUE, OPEN_VALUE, ShadeState
from .const import DOMAIN, _LOGGER
from .coordinator import CrestronCoordinator
from .entity import CrestronEntity

PARALLEL_UPDATES = 1

# Load icons.json file for icon mapping
ICONS_FILE = os.path.join(os.path.dirname(__file__), "icons.json")
try:
    with open(ICONS_FILE, "r") as f:
        ICONS = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    _LOGGER.warning("Could not load icons.json file")
    ICONS = {
        "shade": {
            "default": "mdi:window-shutter",
            "state": {
                "open": "mdi:window-shutter-open",
                "closed": "mdi:window-shutter",
                "opening": "mdi:window-shutter-alert",
                "closing": "mdi:window-shutter-alert",
            },
        }
    }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Crestron shades based on config entry."""
    coordinator: CrestronCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    # Create list of shade entities
    entities = []
    for shade_id, shade in coordinator.shades.items():
        entities.append(CrestronShade(coordinator, shade_id))

    async_add_entities(entities)


class CrestronShade(CrestronEntity, CoverEntity):
    """Representation of a Crestron shade."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    _attr_device_class = CoverDeviceClass.SHADE
    _attr_name = None

    def __init__(self, coordinator: CrestronCoordinator, shade_id: int) -> None:
        """Initialize the shade."""
        super().__init__(coordinator, shade_id)
        # Keep track of last position to determine if we're opening/closing
        self._last_position = self.current_cover_position
        # Set initial icon
        self._attr_icon = ICONS.get("shade", {}).get("default", "mdi:window-shutter")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        shade = self.shade
        if shade is None:
            self._attr_available = False
            return

        # Update last position for opening/closing determination
        self._last_position = self.current_cover_position

        # Update icon based on state
        if self.is_closed:
            self._attr_icon = ICONS.get("shade", {}).get("state", {}).get(
                "closed", "mdi:window-shutter"
            )
        elif self.is_opening:
            self._attr_icon = ICONS.get("shade", {}).get("state", {}).get(
                "opening", "mdi:window-shutter-alert"
            )
        elif self.is_closing:
            self._attr_icon = ICONS.get("shade", {}).get("state", {}).get(
                "closing", "mdi:window-shutter-alert"
            )
        else:
            self._attr_icon = ICONS.get("shade", {}).get("state", {}).get(
                "open", "mdi:window-shutter-open"
            )

        self.async_write_ha_state()

    @property
    def current_cover_position(self) -> int:
        """Return current position of cover."""
        shade = self.shade
        if not shade:
            return 0

        # Convert from 0-65535 to 0-100
        return round(shade.position / OPEN_VALUE * 100)

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self._last_position < self.current_cover_position

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self._last_position > self.current_cover_position

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed or not."""
        shade = self.shade
        if not shade:
            return True
        return shade.position == CLOSED_VALUE

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        shade = self.shade
        if not shade:
            return {}

        return {
            "connection_status": shade.connectionStatus,
            "room_id": shade.roomId,
        }

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.coordinator.open_shade(self._shade_id)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.coordinator.close_shade(self._shade_id)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        # For now we don't have a direct stop command,
        # so we'll set it to the current position to stop movement
        shade = self.shade
        if not shade:
            return
        await self.coordinator.set_shade_position(self._shade_id, shade.position)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        if ATTR_POSITION not in kwargs:
            return

        position = kwargs[ATTR_POSITION]
        # Convert from 0-100 to 0-65535
        raw_position = round(position / 100 * OPEN_VALUE)
        await self.coordinator.set_shade_position(self._shade_id, raw_position)
