"""Shared logic for sync and async clients."""

from __future__ import annotations

import random
from typing import Literal

import httpx

from .exceptions import (
    ERROR_CODE_TO_EXCEPTION,
    AuthenticationError,
    RateLimitedError,
    SharpAPIError,
    TierRestrictedError,
    ValidationError,
    canonical_code,
)
from .models import APIResponse, RateLimitInfo, ResponseMeta

DEFAULT_BASE_URL = "https://api.sharpapi.io"
DEFAULT_TIMEOUT = 30.0
USER_AGENT = "sharpapi-python/0.2.5"

# Supported REST authentication methods. SSE always uses ``?api_key=`` query
# regardless of this setting because EventSource cannot set custom headers.
AuthMethod = Literal["x-api-key", "bearer"]
DEFAULT_AUTH_METHOD: AuthMethod = "x-api-key"

RETRY_STATUSES = frozenset({502, 503, 504})
RETRY_MAX_ATTEMPTS = 3
RETRY_BASE_DELAY = 0.5
RETRY_MAX_DELAY = 4.0


def should_retry(response: httpx.Response | None, exc: Exception | None) -> bool:
    """True for transient upstream failures worth retrying."""
    if exc is not None:
        return isinstance(exc, (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError))
    return response is not None and response.status_code in RETRY_STATUSES


def retry_delay(attempt: int) -> float:
    """Exponential backoff with full jitter. attempt is 1-indexed."""
    ceiling = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
    return random.uniform(0, ceiling)


def parse_response(raw: dict, model_class: type) -> APIResponse:
    """Parse raw API JSON into a typed APIResponse."""
    data_raw = raw.get("data", [])
    if isinstance(data_raw, list):
        items = [model_class.model_validate(item) for item in data_raw]
    else:
        items = [model_class.model_validate(data_raw)]

    meta = None
    meta_raw = raw.get("meta")
    if meta_raw:
        meta = ResponseMeta.model_validate(meta_raw)

    return APIResponse(
        success=raw.get("success"),
        data=items,
        meta=meta,
        timestamp=raw.get("timestamp"),
        tier=raw.get("tier"),
    )


def parse_rate_limit(response: httpx.Response) -> RateLimitInfo:
    """Extract rate limit info from response headers."""
    headers = response.headers
    return RateLimitInfo(
        limit=_int_or_none(headers.get("x-ratelimit-limit")),
        remaining=_int_or_none(headers.get("x-ratelimit-remaining")),
        reset=_float_or_none(headers.get("x-ratelimit-reset")),
        tier=headers.get("x-tier"),
    )


def handle_errors(response: httpx.Response) -> None:
    """Raise typed exceptions for error responses."""
    if response.is_success:
        return

    try:
        body = response.json()
    except Exception:
        body = {}

    error_obj = body.get("error", body)
    if isinstance(error_obj, dict):
        error_msg = error_obj.get("message", error_obj.get("error", f"HTTP {response.status_code}"))
        code = error_obj.get("code", body.get("code", "unknown_error"))
    else:
        error_msg = str(error_obj) if error_obj else f"HTTP {response.status_code}"
        code = body.get("code", "unknown_error")
    status = response.status_code

    # Resolve deprecated code aliases (bad_request, invalid_request → validation_error).
    code = canonical_code(code)

    # Prefer the canonical code→exception mapping for well-known codes; fall back
    # to HTTP-status-based routing for responses that omit an error code.
    exc_class = ERROR_CODE_TO_EXCEPTION.get(code or "")
    if exc_class is TierRestrictedError:
        raise TierRestrictedError(
            error_msg,
            code=code,
            status=status,
            required_tier=body.get("required_tier"),
        )
    if exc_class is RateLimitedError:
        raise RateLimitedError(
            error_msg,
            code=code,
            status=status,
            retry_after=body.get("retry_after"),
        )
    if exc_class is not None and exc_class is not SharpAPIError:
        raise exc_class(error_msg, code=code, status=status)

    # No canonical code match — route by HTTP status.
    if status == 401:
        raise AuthenticationError(error_msg, code=code, status=status)
    elif status == 403:
        raise TierRestrictedError(
            error_msg,
            code=code,
            status=status,
            required_tier=body.get("required_tier"),
        )
    elif status == 429:
        raise RateLimitedError(
            error_msg,
            code=code,
            status=status,
            retry_after=body.get("retry_after"),
        )
    elif status == 400:
        raise ValidationError(error_msg, code=code, status=status)
    else:
        raise SharpAPIError(error_msg, code=code, status=status)


def make_headers(
    api_key: str,
    auth_method: AuthMethod = DEFAULT_AUTH_METHOD,
) -> dict[str, str]:
    """Build default request headers.

    Args:
        api_key: The SharpAPI key (e.g. ``sk_live_...``).
        auth_method: Either ``"x-api-key"`` (default — sends an
            ``X-API-Key`` header) or ``"bearer"`` (sends
            ``Authorization: Bearer <key>``). Useful when proxies, IAM
            layers, or SSO gateways strip non-standard custom headers.
    """
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }
    if auth_method == "bearer":
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        headers["X-API-Key"] = api_key
    return headers


def _int_or_none(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _float_or_none(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
