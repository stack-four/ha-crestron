"""Debug helper for Crestron integration."""
import logging
import importlib
import sys

_LOGGER = logging.getLogger(__name__)


def check_repairs_module():
    """Check what functions are available in the repairs module."""
    try:
        from homeassistant.components import repairs
        module_info = {
            "name": "homeassistant.components.repairs",
            "exists": True,
            "dir": dir(repairs),
        }

        # Check for specific functions
        for func_name in [
            "RepairsFlow",
            "async_create_fix_flow",
            "async_register_issue",
            "async_delete_issue",
            "ISSUE_REGISTRY",
        ]:
            module_info[func_name] = hasattr(repairs, func_name)

        return module_info
    except ImportError:
        return {
            "name": "homeassistant.components.repairs",
            "exists": False,
            "error": "Module not found"
        }


def check_issue_registry():
    """Check what functions are available in the issue registry."""
    try:
        from homeassistant.helpers import issue_registry
        module_info = {
            "name": "homeassistant.helpers.issue_registry",
            "exists": True,
            "dir": dir(issue_registry),
        }

        # Check for specific classes and functions
        for item in [
            "IssueRegistry",
            "IssueSeverity",
            "async_get",
        ]:
            module_info[item] = hasattr(issue_registry, item)

        return module_info
    except ImportError:
        return {
            "name": "homeassistant.helpers.issue_registry",
            "exists": False,
            "error": "Module not found"
        }


def check_config_flow():
    """Check what methods are expected in a config flow."""
    try:
        from homeassistant import config_entries
        module_info = {
            "name": "homeassistant.config_entries",
            "exists": True,
            "ConfigFlow methods": [m for m in dir(config_entries.ConfigFlow) if not m.startswith("_")],
            "OptionsFlow methods": [m for m in dir(config_entries.OptionsFlow) if not m.startswith("_")],
        }
        return module_info
    except ImportError:
        return {
            "name": "homeassistant.config_entries",
            "exists": False,
            "error": "Module not found"
        }


def check_ha_version():
    """Check Home Assistant version."""
    try:
        import homeassistant.const
        return {
            "name": "homeassistant.const",
            "exists": True,
            "__version__": homeassistant.const.__version__,
        }
    except (ImportError, AttributeError):
        return {
            "name": "homeassistant.const",
            "exists": False,
            "error": "Module not found or no __version__ attribute"
        }


def run_diagnostics():
    """Run all diagnostics and print results."""
    checks = {
        "repairs_module": check_repairs_module(),
        "issue_registry": check_issue_registry(),
        "config_flow": check_config_flow(),
        "ha_version": check_ha_version(),
    }

    import json
    print(json.dumps(checks, indent=2))

    return checks


if __name__ == "__main__":
    run_diagnostics()