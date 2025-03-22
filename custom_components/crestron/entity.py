"""Base entity for Crestron integration."""
from __future__ import annotations

from typing import Any, Dict, Optional

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import CrestronCoordinator


class CrestronEntity(CoordinatorEntity[CrestronCoordinator]):
    """Base Crestron entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CrestronCoordinator,
        shade_id: int,
        translation_key: Optional[str] = None,
        entity_category: Optional[EntityCategory] = None,
    ) -> None:
        """Initialize Crestron entity."""
        super().__init__(coordinator)

        self._shade_id = shade_id
        self._attr_translation_key = translation_key
        self._attr_entity_category = entity_category

        # Set up unique ID
        self._attr_unique_id = f"{coordinator.unique_id}_{shade_id}"

        # Get shade from coordinator
        shade = coordinator.shades.get(shade_id, {})
        if shade:
            # Set up device info
            room_id = shade.get("roomId", 0)
            room_name = f"Room {room_id}" if room_id > 0 else "Unknown Room"

            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{coordinator.unique_id}_{shade_id}")},
                name=shade.get("name", f"Shade {shade_id}"),
                manufacturer=MANUFACTURER,
                model="Crestron Shade",
                via_device=(DOMAIN, coordinator.unique_id),
                suggested_area=room_name,
            )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        shade = self.coordinator.shades.get(self._shade_id)
        if not shade:
            return False

        # Check if the shade is online
        return shade.get("connectionStatus", "").lower() == "online"

    @property
    def shade(self):
        """Return the shade object."""
        return self.coordinator.shades.get(self._shade_id)
