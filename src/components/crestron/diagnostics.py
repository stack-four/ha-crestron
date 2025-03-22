"""Diagnostics support for Crestron."""
from __future__ import annotations

from typing import Any, Dict

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_AUTH_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import CrestronCoordinator

TO_REDACT = {CONF_AUTH_TOKEN, CONF_HOST, "name", "manufacturer", "model", "id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> Dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: CrestronCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Get the latest data
    shades_data = {
        shade_id: {
            "position": shade.position,
            "id": shade.id,
            "name": shade.name,
            "connectionStatus": shade.connectionStatus,
            "roomId": shade.roomId,
        }
        for shade_id, shade in coordinator.shades.items()
    }

    devices_data = coordinator.devices

    # Redact sensitive information
    redacted_entry = async_redact_data(entry.as_dict(), TO_REDACT)
    redacted_shades = async_redact_data(shades_data, TO_REDACT)
    redacted_devices = async_redact_data(devices_data, TO_REDACT)

    return {
        "entry": redacted_entry,
        "shades": redacted_shades,
        "devices": redacted_devices,
        "api_status": {
            "host_reachable": coordinator.last_update_success,
            "last_update_success": coordinator.last_update_success,
            "last_exception": str(coordinator.last_exception) if coordinator.last_exception else None,
        }
    }