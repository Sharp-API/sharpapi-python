"""SharpAPI exceptions."""

from __future__ import annotations


class SharpAPIError(Exception):
    """Base exception for all SharpAPI errors."""

    def __init__(self, message: str, code: str | None = None, status: int | None = None):
        super().__init__(message)
        self.code = code
        self.status = status


class AuthenticationError(SharpAPIError):
    """API key is missing or invalid (401)."""


class TierRestrictedError(SharpAPIError):
    """Feature not available on current tier (403)."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        status: int | None = None,
        required_tier: str | None = None,
    ):
        super().__init__(message, code, status)
        self.required_tier = required_tier


class RateLimitedError(SharpAPIError):
    """Too many requests (429)."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        status: int | None = None,
        retry_after: float | None = None,
    ):
        super().__init__(message, code, status)
        self.retry_after = retry_after


class ValidationError(SharpAPIError):
    """Invalid request parameters (400)."""


class StreamError(SharpAPIError):
    """Error during SSE streaming."""
