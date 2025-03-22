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

    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, coordinator: CrestronCoordinator, shade_id: int) -> None:
        """Initialize the shade."""
        super().__init__(coordinator, shade_id)

        shade = coordinator.shades.get(shade_id, {})
        self._attr_name = shade.get("name", f"Shade {shade_id}")
        self._attr_unique_id = f"crestron_shade_{shade_id}"

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        # Get shade state
        position = self.current_cover_position or 0

        if position == 0:
            state = "closed"
        elif position == 100:
            state = "open"
        else:
            state = "default"

        # Use state icons if available
        return ICONS.get("shade", {}).get("state", {}).get(
            state, ICONS.get("shade", {}).get("default", "mdi:window-shutter")
        )

    @property
    def current_cover_position(self) -> Optional[int]:
        """Return current position of cover."""
        shade = self.coordinator.shades.get(self._shade_id, {})
        return shade.get("position", 0)

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        position = self.current_cover_position
        if position is None:
            return False
        return position == 0

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        shade = self.coordinator.shades.get(self._shade_id, {})
        return shade.get("status") == "opening"

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        shade = self.coordinator.shades.get(self._shade_id, {})
        return shade.get("status") == "closing"

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.coordinator.api.open_shade(self._shade_id)
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.coordinator.api.close_shade(self._shade_id)
        await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.coordinator.api.stop_shade(self._shade_id)
        await self.coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs.get(ATTR_POSITION)
        if position is not None:
            await self.coordinator.api.set_position(self._shade_id, position)
            await self.coordinator.async_request_refresh()
