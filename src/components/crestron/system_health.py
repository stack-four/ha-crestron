"""System health for Crestron integration."""
from __future__ import annotations

from typing import Any, Dict

import aiohttp
from homeassistant.components.system_health import SystemHealthRegistration
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, _LOGGER


@callback
def async_register(hass: HomeAssistant, register: SystemHealthRegistration) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> Dict[str, Any]:
    """Get info for the system health info."""
    integrations = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state.recoverable
    ]

    # Count configured hosts and active connections
    configured_hosts = len(integrations)
    active_connections = 0
    api_error_count = 0

    # Check all hosts for active connections
    if DOMAIN in hass.data:
        for entry_id, coordinator in hass.data[DOMAIN].items():
            try:
                if coordinator.last_update_success:
                    active_connections += 1
            except Exception:  # pylint: disable=broad-except
                api_error_count += 1

    return {
        "configured_hosts": configured_hosts,
        "active_connections": active_connections,
        "api_error_count": api_error_count,
    }