"""Repair functions for the Crestron integration."""
from __future__ import annotations

from typing import Any, Dict, Final

import voluptuous as vol

from homeassistant.components.repairs import (
    async_register_issue,
    async_delete_issue,
    ISSUE_REGISTRY,
    RepairsFlow,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.issue_registry import IssueSeverity

from .const import DOMAIN, _LOGGER

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
    data = {"entry_id": entry.entry_id}

    async_register_issue(
        hass,
        domain=DOMAIN,
        issue_id=f"{issue_id}_{entry.entry_id}",
        translation_key=issue_id,
        translation_placeholders=description_placeholders,
        data=data,
        is_fixable=True,
        severity=IssueSeverity.ERROR,
        learn_more_url=f"https://www.home-assistant.io/integrations/{DOMAIN}/#troubleshooting",
    )


class CrestronAuthFailureRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, entry_id: str) -> None:
        """Initialize the repair flow."""
        self.entry_id = entry_id
        super().__init__()

    async def async_step_init(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Initialize the repair flow."""
        if user_input is not None:
            return await self.async_step_confirm()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),  # Empty schema
            description_placeholders={
                "integration_name": "Crestron",
                "issue": "authentication",
            },
        )

    async def async_step_confirm(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            # Trigger a reauthentication flow
            async_delete_issue(
                self.hass,
                domain=DOMAIN,
                issue_id=f"{ISSUE_AUTH_FAILURE}_{self.entry_id}",
            )

            # Start reauthentication flow
            entry = self.hass.config_entries.async_get_entry(self.entry_id)
            if entry:
                self.hass.config_entries.async_start_reauth(self.hass, entry.entry_id)

                # Inform the user that reauth has been started
                return self.async_create_entry(
                    title="",
                    data={},
                )

            raise HomeAssistantError("Failed to start reauthentication")

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),  # Empty schema
            description_placeholders={
                "integration_name": "Crestron",
            },
        )


class CrestronConnectivityRepairFlow(RepairsFlow):
    """Handler for connectivity issue fixing flow."""

    def __init__(self, entry_id: str) -> None:
        """Initialize the repair flow."""
        self.entry_id = entry_id
        super().__init__()

    async def async_step_init(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Initialize the repair flow."""
        if user_input is not None:
            return await self.async_step_confirm()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),  # Empty schema
            description_placeholders={
                "integration_name": "Crestron",
                "issue": "connectivity",
            },
        )

    async def async_step_confirm(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            # Clear the issue
            async_delete_issue(
                self.hass,
                domain=DOMAIN,
                issue_id=f"{ISSUE_CONNECTIVITY}_{self.entry_id}",
            )

            # Reload the entry to try again
            entry = self.hass.config_entries.async_get_entry(self.entry_id)
            if entry:
                self.hass.config_entries.async_reload(entry.entry_id)

                # Inform the user that reload has been started
                return self.async_create_entry(
                    title="",
                    data={},
                )

            raise HomeAssistantError("Failed to reload integration")

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),  # Empty schema
            description_placeholders={
                "integration_name": "Crestron",
            },
        )


class CrestronStaleShadesRepairFlow(RepairsFlow):
    """Handler for stale shades issue fixing flow."""

    def __init__(self, entry_id: str) -> None:
        """Initialize the repair flow."""
        self.entry_id = entry_id
        super().__init__()

    async def async_step_init(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Initialize the repair flow."""
        if user_input is not None:
            return await self.async_step_confirm()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),  # Empty schema
            description_placeholders={
                "integration_name": "Crestron",
                "issue": "stale shades",
            },
        )

    async def async_step_confirm(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            # Clear the issue
            async_delete_issue(
                self.hass,
                domain=DOMAIN,
                issue_id=f"{ISSUE_STALE_SHADES}_{self.entry_id}",
            )

            # Reload the entry to try again
            entry = self.hass.config_entries.async_get_entry(self.entry_id)
            if entry:
                self.hass.config_entries.async_reload(entry.entry_id)

                # Inform the user that reload has been started
                return self.async_create_entry(
                    title="",
                    data={},
                )

            raise HomeAssistantError("Failed to reload integration")

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),  # Empty schema
            description_placeholders={
                "integration_name": "Crestron",
            },
        )


@callback
def register_repair_flows(hass: HomeAssistant) -> None:
    """Register repair flows for Crestron issues."""
    # We no longer use async_create_fix_flow as it's not available
    # Instead, the flows will be automatically registered by Home Assistant
    # when issues are created
    _LOGGER.debug("Registering repair flows for Crestron integration")

    # Register issue handlers in HA's issue registry
    ISSUE_REGISTRY.async_create_issue_handler(
        handler_domain=DOMAIN,
        handler_issue=ISSUE_AUTH_FAILURE,
        flow_handler=lambda data: CrestronAuthFailureRepairFlow(data["entry_id"]),
    )

    ISSUE_REGISTRY.async_create_issue_handler(
        handler_domain=DOMAIN,
        handler_issue=ISSUE_CONNECTIVITY,
        flow_handler=lambda data: CrestronConnectivityRepairFlow(data["entry_id"]),
    )

    ISSUE_REGISTRY.async_create_issue_handler(
        handler_domain=DOMAIN,
        handler_issue=ISSUE_STALE_SHADES,
        flow_handler=lambda data: CrestronStaleShadesRepairFlow(data["entry_id"]),
    )