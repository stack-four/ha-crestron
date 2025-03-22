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

TO_REDACT = {CONF_AUTH_TOKEN}


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
            "pref_disable_new_entities": entry.pref_disable_new_entities,
            "pref_disable_polling": entry.pref_disable_polling,
            "source": entry.source,
            "unique_id": entry.unique_id,
            "disabled_by": entry.disabled_by,
        },
        "devices": [
            {
                "id": device.id,
                "name": device.name,
                "manufacturer": device.manufacturer,
                "model": device.model,
                "identifiers": list(next(iter(device.identifiers), [])),
                "via_device_id": device.via_device_id,
                "disabled": device.disabled,
                "disabled_by": device.disabled_by,
                "entry_type": device.entry_type,
            }
            for device in devices
        ],
        "entities": [
            {
                "id": entity.entity_id,
                "name": entity.name,
                "device_id": entity.device_id,
                "disabled": entity.disabled,
                "disabled_by": entity.disabled_by,
                "entity_category": entity.entity_category,
                "original_name": entity.original_name,
                "platform": entity.platform,
                "unique_id": entity.unique_id,
            }
            for entity in entities
        ],
    }

    # If coordinator exists, get data
    if coordinator:
        try:
            config_data["coordinator"] = {
                "data": async_redact_data(coordinator.data if coordinator.data else {}, TO_REDACT),
                "last_update_success": coordinator.last_update_success,
                "shades_count": len(coordinator.shades) if hasattr(coordinator, "shades") else 0,
            }
        except Exception as ex:
            config_data["coordinator_error"] = str(ex)

    # Include any domain-related data from integration manifest
    try:
        import json
        import os
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.json")
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        config_data["manifest"] = manifest
    except Exception as ex:
        config_data["manifest_error"] = str(ex)

    # Add integration domain for debugging
    config_data["integration_domain"] = DOMAIN

    return config_data