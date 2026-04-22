"""SharpAPI synchronous Python client."""

from __future__ import annotations

import time
from typing import Any

import httpx

from ._base import (
    DEFAULT_AUTH_METHOD,
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    RETRY_MAX_ATTEMPTS,
    AuthMethod,
    handle_errors,
    make_headers,
    parse_rate_limit,
    parse_response,
    retry_delay,
    should_retry,
)
from ._utils import _clean_params
from .models import (
    AccountInfo,
    APIKey,
    APIResponse,
    ArbitrageOpportunity,
    ClosingSnapshot,
    Event,
    EVOpportunity,
    League,
    LowHoldOpportunity,
    Market,
    MiddleOpportunity,
    OddsLine,
    RateLimitInfo,
    Sport,
    Sportsbook,
)
from .streaming import EventStream


class SharpAPI:
    """SharpAPI Python client.

    Provides typed access to odds, +EV, arbitrage, middles, and streaming
    endpoints.

    Args:
        api_key: Your SharpAPI key (e.g. ``sk_live_...``).
        base_url: Override the API base URL (defaults to production).
        timeout: HTTP timeout in seconds.
        auth_method: How to send the API key on REST requests. ``"x-api-key"``
            (default) sends the ``X-API-Key`` header. ``"bearer"`` sends
            ``Authorization: Bearer <key>`` instead — useful when running
            behind IAM layers, SSO, or API gateways that strip custom
            headers. SSE streams always authenticate via ``?api_key=`` query
            (EventSource cannot set headers) and are unaffected.

    Example::

        from sharpapi import SharpAPI

        client = SharpAPI("sk_live_xxx")

        # Or, behind a proxy that requires standard Bearer auth:
        client = SharpAPI("sk_live_xxx", auth_method="bearer")

        # Get arbitrage opportunities
        arbs = client.arbitrage.get(min_profit=1.0)
        for arb in arbs.data:
            print(f"{arb.profit_percent}% — {arb.event_name}")

        # Get +EV opportunities
        evs = client.ev.get(min_ev=3.0, league="nba")
        for opp in evs.data:
            print(f"+{opp.ev_percentage}% on {opp.selection} @ {opp.sportsbook}")

        # Stream real-time updates
        stream = client.stream.opportunities(league="nba")
        for event_type, data in stream.iter_events():
            print(event_type, data)
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        auth_method: AuthMethod = DEFAULT_AUTH_METHOD,
    ):
        if not api_key:
            raise ValueError("api_key is required")

        self._api_key = api_key
        self._auth_method: AuthMethod = auth_method
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._http = httpx.Client(
            base_url=f"{self._base_url}/api/v1",
            headers=make_headers(api_key, auth_method),
            timeout=timeout,
        )
        self._last_rate_limit = RateLimitInfo()

        # Resource namespaces
        self.odds = _OddsResource(self)
        self.ev = _EVResource(self)
        self.arbitrage = _ArbitrageResource(self)
        self.middles = _MiddlesResource(self)
        self.low_hold = _LowHoldResource(self)
        self.sports = _SportsResource(self)
        self.leagues = _LeaguesResource(self)
        self.sportsbooks = _SportsbooksResource(self)
        self.events = _EventsResource(self)
        self.account = _AccountResource(self)
        self.keys = _KeysResource(self)
        self.stream = _StreamResource(self)

    @property
    def rate_limit(self) -> RateLimitInfo:
        """Rate limit info from the last request."""
        return self._last_rate_limit

    def _request(self, method: str, path: str, params: dict | None = None, **kwargs) -> Any:
        """Make an API request and return parsed JSON. Retries 502/503/504 with jittered backoff."""
        if params:
            params = _clean_params(params)

        response: httpx.Response | None = None
        for attempt in range(1, RETRY_MAX_ATTEMPTS + 1):
            exc: Exception | None = None
            try:
                response = self._http.request(method, path, params=params, **kwargs)
            except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError) as e:
                exc = e

            if attempt < RETRY_MAX_ATTEMPTS and should_retry(response, exc):
                time.sleep(retry_delay(attempt))
                continue
            if exc is not None:
                raise exc
            break

        assert response is not None
        self._last_rate_limit = parse_rate_limit(response)
        handle_errors(response)
        return response.json()

    def _get(self, path: str, params: dict | None = None) -> Any:
        return self._request("GET", path, params)

    def _post(self, path: str, json_body: Any = None, params: dict | None = None) -> Any:
        return self._request("POST", path, params, json=json_body)

    def close(self) -> None:
        """Close the HTTP client."""
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# =============================================================================
# Resource Namespaces
# =============================================================================


class _OddsResource:
    """Access odds data."""

    def __init__(self, client: SharpAPI):
        self._client = client

    def get(
        self,
        *,
        sportsbook: str | list[str] | None = None,
        add_sportsbook: str | list[str] | None = None,
        sport: str | list[str] | None = None,
        league: str | list[str] | None = None,
        market: str | list[str] | None = None,
        event: str | list[str] | None = None,
        live: bool | None = None,
        sort: str | None = None,
        group_by: str | None = None,
        fields: str | list[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> APIResponse[list[OddsLine]]:
        """Get current odds snapshot.

        Args:
            sportsbook: Filter by sportsbook(s).
            add_sportsbook: Add sportsbook(s) beyond tier defaults.
            sport: Filter by sport(s).
            league: Filter by league(s).
            market: Filter by market type(s).
            event: Filter by event ID(s).
            live: Filter by live status.
            sort: Sort field (prefix with - for descending).
            group_by: Group results (e.g. "event").
            fields: Cherry-pick response fields.
            limit: Max results (1-500, default 50).
            offset: Pagination offset.
        """
        data = self._client._get("/odds", {
            "sportsbook": sportsbook,
            "add_sportsbook": add_sportsbook,
            "sport": sport,
            "league": league,
            "market": market,
            "event": event,
            "live": live,
            "sort": sort,
            "group_by": group_by,
            "fields": fields,
            "limit": limit,
            "offset": offset,
        })
        return _parse_response(data, OddsLine)

    def best(
        self,
        *,
        sport: str | list[str] | None = None,
        league: str | list[str] | None = None,
        market: str | list[str] | None = None,
        event: str | list[str] | None = None,
        live: bool | None = None,
        sportsbook: str | list[str] | None = None,
        add_sportsbook: str | list[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> APIResponse[list[OddsLine]]:
        """Get best odds per selection across all sportsbooks."""
        data = self._client._get("/odds/best", {
            "sport": sport,
            "league": league,
            "market": market,
            "event": event,
            "live": live,
            "sportsbook": sportsbook,
            "add_sportsbook": add_sportsbook,
            "limit": limit,
            "offset": offset,
        })
        return _parse_response(data, OddsLine)

    def comparison(
        self,
        event_id: str,
        *,
        market: str | None = None,
    ) -> APIResponse[list[OddsLine]]:
        """Get side-by-side odds comparison for an event."""
        data = self._client._get("/odds/comparison", {
            "event_id": event_id,
            "market": market,
        })
        return _parse_response(data, OddsLine)

    def batch(self, event_ids: list[str]) -> APIResponse[list[OddsLine]]:
        """Batch odds lookup for multiple events."""
        data = self._client._post("/odds/batch", {"event_ids": event_ids})
        return _parse_response(data, OddsLine)

    def closing(
        self,
        event_id: str,
        *,
        sportsbook: str | None = None,
    ) -> ClosingSnapshot:
        """Get closing-line snapshot for an event.

        Returns the captured closing odds grouped by sportsbook. If no
        closing data has been captured for the event, the returned
        ``ClosingSnapshot.books`` mapping will be empty.

        Args:
            event_id: Event ID to fetch closing odds for.
            sportsbook: Optional sportsbook filter (single book ID).
        """
        data = self._client._get("/odds/closing", {
            "event_id": event_id,
            "sportsbook": sportsbook or None,
        })
        raw = data.get("data", data)
        return ClosingSnapshot.model_validate(raw)


class _EVResource:
    """Access +EV opportunities."""

    def __init__(self, client: SharpAPI):
        self._client = client

    def get(
        self,
        *,
        sport: str | list[str] | None = None,
        league: str | list[str] | None = None,
        sportsbook: str | list[str] | None = None,
        add_sportsbook: str | list[str] | None = None,
        market: str | list[str] | None = None,
        min_ev: float | None = None,
        max_ev: float | None = None,
        min_market_width: float | None = None,
        max_market_width: float | None = None,
        max_odds_age: int | None = None,
        date_range: str | None = None,
        live: bool | None = None,
        sort: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> APIResponse[list[EVOpportunity]]:
        """Get +EV opportunities.

        Requires Pro tier or higher.

        Args:
            sport: Filter by sport(s).
            league: Filter by league(s).
            sportsbook: Filter by sportsbook(s).
            add_sportsbook: Add sportsbook(s) beyond tier defaults.
            market: Filter by market type(s).
            min_ev: Minimum EV percentage (default: server-side 0).
            max_ev: Maximum EV percentage.
            min_market_width: Minimum market width.
            max_market_width: Maximum market width.
            max_odds_age: Max age of underlying odds in seconds.
            date_range: "today", "tomorrow", or "week".
            live: Filter live/prematch.
            sort: Sort field ("-ev" default, "confidence", "kelly", "time", "book_count").
            limit: Max results (1-500, default 50).
            offset: Pagination offset.
        """
        data = self._client._get("/opportunities/ev", {
            "sport": sport,
            "league": league,
            "sportsbook": sportsbook,
            "add_sportsbook": add_sportsbook,
            "market": market,
            "min_ev": min_ev,
            "max_ev": max_ev,
            "min_market_width": min_market_width,
            "max_market_width": max_market_width,
            "max_odds_age": max_odds_age,
            "date_range": date_range,
            "live": live,
            "sort": sort,
            "limit": limit,
            "offset": offset,
        })
        return _parse_response(data, EVOpportunity)


class _ArbitrageResource:
    """Access arbitrage opportunities."""

    def __init__(self, client: SharpAPI):
        self._client = client

    def get(
        self,
        *,
        sport: str | list[str] | None = None,
        league: str | list[str] | None = None,
        sportsbook: str | list[str] | None = None,
        add_sportsbook: str | list[str] | None = None,
        market: str | list[str] | None = None,
        min_profit: float | None = None,
        max_odds_age: int | None = None,
        live: bool | None = None,
        sort: str | None = None,
        group: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> APIResponse[list[ArbitrageOpportunity]]:
        """Get arbitrage opportunities.

        Requires Hobby tier or higher.

        Args:
            sport: Filter by sport(s).
            league: Filter by league(s).
            sportsbook: Filter by sportsbook(s).
            add_sportsbook: Add sportsbook(s) beyond tier defaults.
            market: Filter by market type(s).
            min_profit: Minimum profit percentage (default: 0.5).
            max_odds_age: Max age of odds in seconds.
            live: Filter live/prematch.
            sort: Sort field ("-profit" default, "time", "sport", "market").
            group: "best" = highest-profit per event+market.
            limit: Max results (1-500, default 50).
            offset: Pagination offset.
        """
        data = self._client._get("/opportunities/arbitrage", {
            "sport": sport,
            "league": league,
            "sportsbook": sportsbook,
            "add_sportsbook": add_sportsbook,
            "market": market,
            "min_profit": min_profit,
            "max_odds_age": max_odds_age,
            "live": live,
            "sort": sort,
            "group": group,
            "limit": limit,
            "offset": offset,
        })
        return _parse_response(data, ArbitrageOpportunity)

    def csv(
        self,
        *,
        sport: str | list[str] | None = None,
        league: str | list[str] | None = None,
        min_profit: float | None = None,
        limit: int | None = None,
    ) -> str:
        """Get arbitrage opportunities as CSV text."""
        data = self._client._get("/opportunities/arbitrage", {
            "sport": sport,
            "league": league,
            "min_profit": min_profit,
            "limit": limit,
            "format": "csv",
        })
        # CSV format returns raw text, but our _get parses JSON.
        # The server returns JSON-wrapped CSV or raw text.
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return str(data)


class _MiddlesResource:
    """Access middle opportunities."""

    def __init__(self, client: SharpAPI):
        self._client = client

    def get(
        self,
        *,
        sport: str | list[str] | None = None,
        league: str | list[str] | None = None,
        sportsbook: str | list[str] | None = None,
        market: str | list[str] | None = None,
        min_size: float | None = None,
        max_odds_age: int | None = None,
        live: bool | None = None,
        state: str | None = None,
        sort: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> APIResponse[list[MiddleOpportunity]]:
        """Get middle opportunities.

        Requires Pro tier or higher.

        Args:
            sport: Filter by sport(s).
            league: Filter by league(s).
            sportsbook: Filter by sportsbook(s).
            market: Filter by market type(s) ("point_spread", "total_points").
            min_size: Minimum middle size in points (default: 0.5).
            max_odds_age: Max age of odds in seconds.
            live: Filter live/prematch.
            state: US state for deep links (default: "pa").
            sort: Sort field ("quality" default, "ev", "probability", "middle_size").
            limit: Max results (1-500, default 50).
            offset: Pagination offset.
        """
        data = self._client._get("/opportunities/middles", {
            "sport": sport,
            "league": league,
            "sportsbook": sportsbook,
            "market": market,
            "min_size": min_size,
            "max_odds_age": max_odds_age,
            "live": live,
            "state": state,
            "sort": sort,
            "limit": limit,
            "offset": offset,
        })
        return _parse_response(data, MiddleOpportunity)


class _LowHoldResource:
    """Access low-hold (low vig) opportunities."""

    def __init__(self, client: SharpAPI):
        self._client = client

    def get(
        self,
        *,
        sport: str | list[str] | None = None,
        league: str | list[str] | None = None,
        sportsbook: str | list[str] | None = None,
        market: str | list[str] | None = None,
        max_hold: float | None = None,
        live: bool | None = None,
        state: str | None = None,
        sort: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> APIResponse[list[LowHoldOpportunity]]:
        """Get low-hold opportunities.

        Args:
            sport: Filter by sport(s).
            league: Filter by league(s).
            sportsbook: Filter by sportsbook(s).
            market: Filter by market type(s).
            max_hold: Maximum hold/vig percentage (default: 5.0).
            live: Filter live/prematch.
            state: US state for deep links.
            sort: Sort field ("hold" default, "market", "sport").
            limit: Max results (1-500, default 50).
            offset: Pagination offset.
        """
        data = self._client._get("/opportunities/low_hold", {
            "sport": sport,
            "league": league,
            "sportsbook": sportsbook,
            "market": market,
            "max_hold": max_hold,
            "live": live,
            "state": state,
            "sort": sort,
            "limit": limit,
            "offset": offset,
        })
        return _parse_response(data, LowHoldOpportunity)


class _SportsResource:
    def __init__(self, client: SharpAPI):
        self._client = client

    def list(self) -> APIResponse[list[Sport]]:
        """List all available sports."""
        data = self._client._get("/sports")
        return _parse_response(data, Sport)

    def get(self, sport_id: str) -> Sport:
        """Get a specific sport."""
        data = self._client._get(f"/sports/{sport_id}")
        raw = data.get("data", data)
        return Sport.model_validate(raw)


class _LeaguesResource:
    def __init__(self, client: SharpAPI):
        self._client = client

    def list(self, *, sport: str | None = None) -> APIResponse[list[League]]:
        """List all leagues, optionally filtered by sport."""
        data = self._client._get("/leagues", {"sport": sport})
        return _parse_response(data, League)

    def get(self, league_id: str) -> League:
        """Get a specific league."""
        data = self._client._get(f"/leagues/{league_id}")
        raw = data.get("data", data)
        return League.model_validate(raw)


class _SportsbooksResource:
    def __init__(self, client: SharpAPI):
        self._client = client

    def list(self) -> APIResponse[list[Sportsbook]]:
        """List all active sportsbooks."""
        data = self._client._get("/sportsbooks")
        return _parse_response(data, Sportsbook)

    def get(self, book_id: str) -> Sportsbook:
        """Get a specific sportsbook."""
        data = self._client._get(f"/sportsbooks/{book_id}")
        raw = data.get("data", data)
        return Sportsbook.model_validate(raw)


class _EventsResource:
    def __init__(self, client: SharpAPI):
        self._client = client

    def list(
        self,
        *,
        sport: str | None = None,
        league: str | list[str] | None = None,
        live: bool | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> APIResponse[list[Event]]:
        """List events."""
        data = self._client._get("/events", {
            "sport": sport,
            "league": league,
            "live": live,
            "limit": limit,
            "offset": offset,
        })
        return _parse_response(data, Event)

    def get(self, event_id: str) -> Event:
        """Get a specific event."""
        data = self._client._get(f"/events/{event_id}")
        raw = data.get("data", data)
        return Event.model_validate(raw)

    def markets(self, event_id: str) -> APIResponse[list[Market]]:
        """List the markets available on a specific event."""
        data = self._client._get(f"/events/{event_id}/markets")
        return _parse_response(data, Market)


class _AccountResource:
    def __init__(self, client: SharpAPI):
        self._client = client

    def me(self) -> AccountInfo:
        """Get current account info (tier, limits, features)."""
        data = self._client._get("/account")
        raw = data.get("data", data)
        return AccountInfo.model_validate(raw)

    def usage(self) -> dict:
        """Get current usage stats."""
        data = self._client._get("/account/usage")
        return data.get("data", data)


class _KeysResource:
    """Manage API keys on the current account.

    Wraps the ``/account/keys`` CRUD endpoints. Requires authentication
    with a key whose user has permission to manage keys (typically a
    dashboard-issued key).
    """

    def __init__(self, client: SharpAPI):
        self._client = client

    def list(self) -> APIResponse[list[APIKey]]:
        """List all API keys on the account."""
        data = self._client._get("/account/keys")
        return _parse_response(data, APIKey)

    def create(self, name: str) -> APIKey:
        """Create a new API key.

        Returns the new ``APIKey`` including the one-time ``key`` secret
        in ``APIKey.key``. Store it securely — it will not be shown again.
        """
        data = self._client._post("/account/keys", {"name": name})
        raw = data.get("data", data)
        return APIKey.model_validate(raw)

    def revoke(self, key_id: str) -> None:
        """Revoke (delete) an API key by ID."""
        self._client._request("DELETE", f"/account/keys/{key_id}")

    def rotate(self, key_id: str) -> APIKey:
        """Rotate an API key — issues a new key and revokes the old one.

        Returns the newly created ``APIKey`` (including the one-time
        ``key`` secret).
        """
        data = self._client._post(f"/account/keys/{key_id}/rotate")
        raw = data.get("data", data)
        # Rotate response shape is {"data": {"new_key": {...}, "old_key": {...}}}
        if isinstance(raw, dict) and "new_key" in raw:
            return APIKey.model_validate(raw["new_key"])
        return APIKey.model_validate(raw)


class _StreamResource:
    """Build SSE stream connections."""

    def __init__(self, client: SharpAPI):
        self._client = client

    def _build_stream(self, path: str, params: dict | None = None) -> EventStream:
        cleaned = _clean_params(params or {})
        cleaned["api_key"] = self._client._api_key
        query = "&".join(f"{k}={v}" for k, v in cleaned.items())
        url = f"{self._client._base_url}/api/v1{path}?{query}"
        return EventStream(
            url=url,
            headers={"X-API-Key": self._client._api_key},
        )

    def odds(
        self,
        *,
        sportsbook: str | list[str] | None = None,
        league: str | list[str] | None = None,
        sport: str | list[str] | None = None,
        market: str | list[str] | None = None,
    ) -> EventStream:
        """Stream real-time odds updates.

        Requires WebSocket add-on or Enterprise tier.

        Returns an EventStream. Use .connect() to block or .iter_events()
        to iterate.
        """
        return self._build_stream("/stream", {
            "channel": "odds",
            "sportsbook": sportsbook,
            "league": league,
            "sport": sport,
            "market": market,
        })

    def opportunities(
        self,
        *,
        sportsbook: str | list[str] | None = None,
        league: str | list[str] | None = None,
        sport: str | list[str] | None = None,
        market: str | list[str] | None = None,
        min_ev: float | None = None,
        min_profit: float | None = None,
    ) -> EventStream:
        """Stream real-time opportunity alerts (EV, arb, middles).

        Requires WebSocket add-on or Enterprise tier.
        """
        return self._build_stream("/stream", {
            "channel": "opportunities",
            "sportsbook": sportsbook,
            "league": league,
            "sport": sport,
            "market": market,
            "min_ev": min_ev,
            "min_profit": min_profit,
        })

    def all(
        self,
        *,
        sportsbook: str | list[str] | None = None,
        league: str | list[str] | None = None,
        sport: str | list[str] | None = None,
        market: str | list[str] | None = None,
    ) -> EventStream:
        """Stream all data (odds + opportunities).

        Requires WebSocket add-on or Enterprise tier.
        """
        return self._build_stream("/stream", {
            "channel": "all",
            "sportsbook": sportsbook,
            "league": league,
            "sport": sport,
            "market": market,
        })

    def event(
        self,
        event_id: str,
        *,
        sportsbook: str | list[str] | None = None,
        market: str | list[str] | None = None,
    ) -> EventStream:
        """Stream updates for a single event."""
        return self._build_stream(f"/stream/events/{event_id}", {
            "sportsbook": sportsbook,
            "market": market,
        })


# =============================================================================
# Helpers
# =============================================================================


_parse_response = parse_response
