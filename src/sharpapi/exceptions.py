"""SharpAPI exceptions and canonical error-code registry.

The error codes here mirror ``pkg/errcodes/errcodes.go`` in sharp-api-go, which
is the single source of truth for every code the API emits. Keep this file in
sync when new codes are added upstream.
"""

from __future__ import annotations


class SharpAPIError(Exception):
    """Base exception for all SharpAPI errors."""

    def __init__(self, message: str, code: str | None = None, status: int | None = None):
        super().__init__(message)
        self.code = code
        self.status = status


class AuthenticationError(SharpAPIError):
    """API key is missing, invalid, expired, disabled, or token is rejected.

    Raised for HTTP 401 responses and any of the auth-related error codes
    (``missing_api_key``, ``invalid_api_key``, ``expired_api_key``,
    ``disabled_api_key``, ``invalid_token``, ``unauthorized``).
    """


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
    """Too many requests (429) — rate-limited, backpressure, or concurrent cap."""

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
    """Error during SSE or WebSocket streaming."""


# =============================================================================
# Canonical error-code registry
#
# Mirrors sharp-api-go/pkg/errcodes/errcodes.go. When upstream adds a new code,
# add it here too and update the matching description. Each code maps to the
# Python exception class that ``handle_errors`` (in ``_base.py``) raises for it.
# =============================================================================

# HTTP error codes — emitted via REST handlers (httputil.WriteJSONError).
BACKPRESSURE = "backpressure"
CONCURRENT_REQUEST_CAP = "concurrent_request_cap"
DISABLED_API_KEY = "disabled_api_key"
EXPIRED_API_KEY = "expired_api_key"
GONE = "gone"
INTERNAL_ERROR = "internal_error"
INVALID_API_KEY = "invalid_api_key"
INVALID_TOKEN = "invalid_token"
METHOD_NOT_ALLOWED = "method_not_allowed"
MISSING_API_KEY = "missing_api_key"
NOT_FOUND = "not_found"
NOT_READY = "not_ready"
RATE_LIMITED = "rate_limited"
SERVICE_UNAVAILABLE = "service_unavailable"
TIER_RESTRICTED = "tier_restricted"
TOO_MANY_STREAMS = "too_many_streams"
UNAUTHORIZED = "unauthorized"
UNKNOWN_ENDPOINT = "unknown_endpoint"
UPSTREAM_ERROR = "upstream_error"
VALIDATION_ERROR = "validation_error"

# WebSocket frame error codes — emitted in "error" message frames.
WS_ALREADY_AUTHENTICATED = "already_authenticated"
WS_INVALID_MESSAGE = "invalid_message"
WS_MISSING_CHANNELS = "missing_channels"
WS_MISSING_TOKEN = "missing_token"
WS_NOT_AUTHENTICATED = "not_authenticated"
WS_UNKNOWN_MESSAGE_TYPE = "unknown_message_type"

#: Human-readable descriptions for every canonical code.
ERROR_CODE_DESCRIPTIONS: dict[str, str] = {
    # HTTP
    BACKPRESSURE: "Server is shedding load; retry shortly.",
    CONCURRENT_REQUEST_CAP: "Too many in-flight requests for this API key.",
    DISABLED_API_KEY: "API key has been disabled.",
    EXPIRED_API_KEY: "API key has expired.",
    GONE: "Resource is no longer available.",
    INTERNAL_ERROR: "Unexpected server error.",
    INVALID_API_KEY: "API key is invalid.",
    INVALID_TOKEN: "Bearer token is invalid or malformed.",
    METHOD_NOT_ALLOWED: "HTTP method not allowed on this endpoint.",
    MISSING_API_KEY: "No API key provided.",
    NOT_FOUND: "Resource not found.",
    NOT_READY: "A required backing store is not yet ready to serve this request; retry shortly.",
    RATE_LIMITED: "Rate limit exceeded; see Retry-After header.",
    SERVICE_UNAVAILABLE: "Service is temporarily unavailable.",
    TIER_RESTRICTED: "Current subscription tier does not include this feature.",
    TOO_MANY_STREAMS: "Maximum concurrent WebSocket/SSE streams exceeded.",
    UNAUTHORIZED: "Authentication required.",
    UNKNOWN_ENDPOINT: "Endpoint does not exist.",
    UPSTREAM_ERROR: "Upstream data source error.",
    VALIDATION_ERROR: "Request parameters failed validation.",
    # WebSocket
    WS_ALREADY_AUTHENTICATED: "Auth frame sent on an already-authenticated connection.",
    WS_INVALID_MESSAGE: "Malformed WebSocket frame.",
    WS_MISSING_CHANNELS: "Subscribe frame had no channels.",
    WS_MISSING_TOKEN: "Auth frame had no token.",
    WS_NOT_AUTHENTICATED: "Action requires authentication first.",
    WS_UNKNOWN_MESSAGE_TYPE: "Unknown WebSocket message type.",
}

#: Map each canonical code to the SharpAPIError subclass ``handle_errors`` raises.
ERROR_CODE_TO_EXCEPTION: dict[str, type[SharpAPIError]] = {
    # Auth family → AuthenticationError
    MISSING_API_KEY: AuthenticationError,
    INVALID_API_KEY: AuthenticationError,
    EXPIRED_API_KEY: AuthenticationError,
    DISABLED_API_KEY: AuthenticationError,
    INVALID_TOKEN: AuthenticationError,
    UNAUTHORIZED: AuthenticationError,
    # Tier
    TIER_RESTRICTED: TierRestrictedError,
    # Rate / load shedding
    RATE_LIMITED: RateLimitedError,
    BACKPRESSURE: RateLimitedError,
    CONCURRENT_REQUEST_CAP: RateLimitedError,
    TOO_MANY_STREAMS: RateLimitedError,
    # Validation
    VALIDATION_ERROR: ValidationError,
    # Streaming frames
    WS_ALREADY_AUTHENTICATED: StreamError,
    WS_INVALID_MESSAGE: StreamError,
    WS_MISSING_CHANNELS: StreamError,
    WS_MISSING_TOKEN: StreamError,
    WS_NOT_AUTHENTICATED: StreamError,
    WS_UNKNOWN_MESSAGE_TYPE: StreamError,
    # Everything else falls through to SharpAPIError
    GONE: SharpAPIError,
    INTERNAL_ERROR: SharpAPIError,
    METHOD_NOT_ALLOWED: SharpAPIError,
    NOT_FOUND: SharpAPIError,
    NOT_READY: SharpAPIError,
    SERVICE_UNAVAILABLE: SharpAPIError,
    UNKNOWN_ENDPOINT: SharpAPIError,
    UPSTREAM_ERROR: SharpAPIError,
}

# Deprecated aliases. ``bad_request`` and ``invalid_request`` were both collapsed
# into ``validation_error`` in sharp-api-go. Kept here so that older API
# responses (or user code still checking these strings) resolve correctly.
# TODO: remove after 2026-10.
DEPRECATED_CODE_ALIASES: dict[str, str] = {
    "bad_request": VALIDATION_ERROR,
    "invalid_request": VALIDATION_ERROR,
}


def canonical_code(code: str | None) -> str | None:
    """Return the canonical code, resolving deprecated aliases."""
    if code is None:
        return None
    return DEPRECATED_CODE_ALIASES.get(code, code)
