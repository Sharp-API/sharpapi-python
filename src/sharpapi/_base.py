"""Shared logic for sync and async clients."""

from __future__ import annotations

import httpx

from .exceptions import (
    AuthenticationError,
    RateLimitedError,
    SharpAPIError,
    TierRestrictedError,
    ValidationError,
)
from .models import APIResponse, RateLimitInfo, ResponseMeta

DEFAULT_BASE_URL = "https://api.sharpapi.io"
DEFAULT_TIMEOUT = 30.0
USER_AGENT = "sharpapi-python/0.2.0"


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


def make_headers(api_key: str) -> dict[str, str]:
    """Build default request headers."""
    return {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }


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
