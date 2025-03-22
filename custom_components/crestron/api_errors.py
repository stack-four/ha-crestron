"""Crestron API errors."""
from __future__ import annotations


class ApiError(Exception):
    """General API error."""


class ApiAuthError(ApiError):
    """API authentication error."""


class ApiConnectionError(ApiError):
    """API connection error."""


class ApiTimeoutError(ApiError):
    """API timeout error."""


class UnsupportedFeatureError(Exception):
    """Exception raised when a feature is not supported."""