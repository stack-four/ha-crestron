"""Exceptions for the Crestron integration."""
from __future__ import annotations

from typing import Any


class CrestronError(Exception):
    """Base class for Crestron exceptions."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the exception."""
        super().__init__(*args)
        self.kwargs = kwargs


class ApiAuthError(CrestronError):
    """Exception raised for authentication errors."""


class ApiError(CrestronError):
    """Exception raised for API errors."""


class ApiConnectionError(CrestronError):
    """Exception raised for connection errors."""


class ApiTimeoutError(CrestronError):
    """Exception raised for timeout errors."""


class UnsupportedFeatureError(CrestronError):
    """Exception raised when a feature is not supported."""