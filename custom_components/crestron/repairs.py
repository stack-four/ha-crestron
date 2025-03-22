"""Repair functions for the Crestron integration."""
from __future__ import annotations

from typing import Any, Dict, Final
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Issue IDs
ISSUE_AUTH_FAILURE: Final = "auth_failure"
ISSUE_CONNECTIVITY: Final = "connectivity"
ISSUE_STALE_SHADES: Final = "stale_shades"


@callback
def async_create_issue(
    hass: HomeAssistant,
    issue_id: str,
    entry: ConfigEntry,
    description_placeholders: Dict[str, str] | None = None,
) -> None:
    """Create an issue that needs to be fixed by the user."""
    # Log the issue for now since we can't safely use the issue registry
    _LOGGER.warning(
        "Issue detected with Crestron integration: %s (entry_id: %s, details: %s)",
        issue_id,
        entry.entry_id,
        description_placeholders or {},
    )
    # We don't actually register the issue as that functionality isn't available