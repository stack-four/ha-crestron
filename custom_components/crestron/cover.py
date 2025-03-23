"""Cover platform for Crestron integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HOST, CONF_PORT, DOMAIN, MANUFACTURER
from .coordinator import CrestronCoordinator

_LOGGER = logging.getLogger(__name__)

# Feature flags
SUPPORT_CRESTRON_SHADE = (
    CoverEntityFeature.OPEN
    | CoverEntityFeature.CLOSE
    | CoverEntityFeature.STOP
    | CoverEntityFeature.SET_POSITION
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Crestron cover devices."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Get the host from entry data
    host = entry.data[CONF_HOST]

    # Get port if available
    port = entry.data.get(CONF_PORT, "")

    # Build a consistent hub identifier
    hub_id = f"crestron_{host}"
    if port:
        hub_id = f"crestron_{host}:{port}"

    # Create the hub device registry
    device_registry = dr.async_get(hass)

    # Check for existing shades and look for what hub identifier they're using
    existing_hub_id = None
    for device in device_registry.devices.values():
        # Check if this is one of our shades
        if any(identifier[0] == DOMAIN and identifier[1].startswith("crestron_shade_")
               for identifier in device.identifiers):
            # Get its via_device reference
            if device.via_device_id:
                via_device = device_registry.async_get(device.via_device_id)
                if via_device:
                    existing_hub_id = next((identifier[1] for identifier in via_device.identifiers
                                         if identifier[0] == DOMAIN), None)
                    if existing_hub_id:
                        _LOGGER.debug("Found existing hub device with ID: %s", existing_hub_id)
                        break

    # If no existing hub ID found, create one with consistent format
    if not existing_hub_id:
        existing_hub_id = hub_id

    # Create or update the hub device with the correct identifier
    hub_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, existing_hub_id)},  # Using existing ID format if found
        manufacturer=MANUFACTURER,
        name=f"Crestron Controller ({host})",
        model="Crestron Shade Controller",
    )

    # Get all shades from the coordinator
    entities = []
    for shade_id, shade_data in coordinator.shades.items():
        entities.append(
            CrestronShade(
                coordinator,
                shade_id,
                shade_data,
                existing_hub_id  # Using the existing ID format
            )
        )

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.info("No shade entities found for Crestron integration")


class CrestronShade(CoordinatorEntity, CoverEntity):
    """Representation of a Crestron shade."""

    _attr_has_entity_name = True
    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features = SUPPORT_CRESTRON_SHADE

    def __init__(
        self,
        coordinator: CrestronCoordinator,
        shade_id: int,
        shade_data: dict[str, Any],
        hub_device_id: str,
    ) -> None:
        """Initialize the shade."""
        super().__init__(coordinator)

        # Store shade details
        self._shade_id = shade_id
        self._shade_data = shade_data
        self._hub_device_id = hub_device_id

        # Set entity attributes
        self._attr_unique_id = f"crestron_shade_{shade_id}"
        self._attr_name = shade_data.get("name", f"Shade {shade_id}")

        # Set up device info with the correct hub identifier
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"crestron_shade_{shade_id}")},
            manufacturer=MANUFACTURER,
            model="Crestron Shade",
            name=self._attr_name,
            via_device=(DOMAIN, self._hub_device_id),
        )

        # Update state
        self._update_attributes()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._shade_id in self.coordinator.shades:
            self._shade_data = self.coordinator.shades[self._shade_id]
            self._update_attributes()
        self.async_write_ha_state()

    def _update_attributes(self) -> None:
        """Update entity attributes based on coordinator data."""
        # Position is from 0 (closed) to 100 (open)
        position = self._shade_data.get("position", 0)

        # Convert percentage position to HA's scale (0-100)
        self._attr_current_position = position

        # Determine if the shade is open, closed, or in between
        self._attr_is_closed = position == 0
        self._attr_is_opening = False
        self._attr_is_closing = False

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        success = await self.coordinator.open_shade(self._shade_id)
        if not success:
            # Operation failed, restore previous state
            self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        success = await self.coordinator.close_shade(self._shade_id)
        if not success:
            # Operation failed, restore previous state
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        success = await self.coordinator.stop_shade(self._shade_id)
        if not success:
            # Operation failed, restore previous state
            self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        if ATTR_POSITION in kwargs:
            success = await self.coordinator.set_shade_position(
                self._shade_id, kwargs[ATTR_POSITION]
            )
            if not success:
                # Operation failed, restore previous state
                self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Entity is available if we have shade data and coordinator is connected
        shade_data = self.coordinator.shades.get(self._shade_id)
        return shade_data is not None and self.coordinator.is_connected

    @property
    def assumed_state(self) -> bool:
        """Return if the state is assumed."""
        # If the coordinator had a failed update but we still have data, the state is assumed
        return not self.coordinator.last_update_success and self._shade_id in self.coordinator.shades