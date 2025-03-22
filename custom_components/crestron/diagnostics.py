"""Diagnostics support for Crestron."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import CONF_AUTH_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

TO_REDACT = [CONF_AUTH_TOKEN]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    _LOGGER.debug("Generating diagnostics for Crestron integration")

    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    # Get all devices for this entry
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    # Get all entities for this entry
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    # Collect configuration data
    config_data = {
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
            "source": entry.source,
            "unique_id": entry.unique_id,
        },
        "devices": [
            {
                "id": device.id,
                "name": device.name,
                "manufacturer": device.manufacturer,
                "model": device.model,
                "disabled": device.disabled,
            }
            for device in devices
        ],
        "entities": [
            {
                "id": entity.entity_id,
                "name": entity.name,
                "device_id": entity.device_id,
                "disabled": entity.disabled,
                "platform": entity.platform,
                "unique_id": entity.unique_id,
            }
            for entity in entities
        ],
    }

    # If coordinator exists, get basic data
    if coordinator:
        try:
            config_data["coordinator"] = {
                "last_update_success": coordinator.last_update_success,
                "shades_count": len(coordinator.shades) if hasattr(coordinator, "shades") else 0,
            }
        except Exception as ex:
            config_data["coordinator_error"] = str(ex)

    # Add integration domain for debugging
    config_data["integration_domain"] = DOMAIN

    return config_data