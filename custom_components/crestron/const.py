"""Constants for the Crestron integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "crestron"
MANUFACTURER: Final = "Crestron"

# Config flow constants
CONF_HOST: Final = "host"
CONF_AUTH_TOKEN: Final = "auth_token"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Default values
DEFAULT_SCAN_INTERVAL: Final = 30
DEFAULT_NAME: Final = "Crestron"

# Update interval
UPDATE_INTERVAL: Final = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

# Service constants
SERVICE_SET_POSITION: Final = "set_position"
SERVICE_OPEN_SHADE: Final = "open_shade"
SERVICE_CLOSE_SHADE: Final = "close_shade"
SERVICE_STOP_SHADE: Final = "stop_shade"

# Attribute constants
ATTR_POSITION: Final = "position"
ATTR_SHADE_ID: Final = "shade_id"
ATTR_SHADE_POSITION: Final = "shade_position"
ATTR_CONNECTION_STATUS: Final = "connection_status"
ATTR_ROOM_ID: Final = "room_id"
ATTR_ROOM_NAME: Final = "room_name"

# Device information
DEV_SHADES_API: Final = "Shades API"
DEV_CRESTRON_HUB: Final = "Crestron Hub"

# Events
EVENT_SHADE_UPDATED: Final = f"{DOMAIN}_shade_updated"
EVENT_CONNECTION_STATUS_CHANGED: Final = f"{DOMAIN}_connection_status_changed"

# Logger
_LOGGER = logging.getLogger(__package__)
LOGGER = logging.getLogger(__name__)
