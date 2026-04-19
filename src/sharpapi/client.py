"""SharpAPI synchronous Python client."""

from __future__ import annotations

import time
from typing import Any, Optional, Union

import httpx

from ._base import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    RETRY_MAX_ATTEMPTS,
    handle_errors,
    make_headers,
    parse_rate_limit,
    parse_response,
    retry_delay,
    should_retry,
)
from ._utils import _clean_params
from .models import (
    APIResponse,
    AccountInfo,
    ArbitrageOpportunity,
    EVOpportunity,
    Event,
    League,
    LowHoldOpportunity,
    MiddleOpportunity,
    OddsLine,
    RateLimitInfo,
    Sportsbook,
    Sport,
)
from .streaming import EventStream


class SharpAPI:
    """SharpAPI Python client.

    Provides typed access to odds, +EV, arbitrage, middles, and streaming
    endpoints.

    Example::

        from sharpapi import SharpAPI

        client = SharpAPI("sk_live_xxx")

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
    ):
        if not api_key:
            raise ValueError("api_key is required")

        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._http = httpx.Client(
            base_url=f"{self._base_url}/api/v1",
            headers=make_headers(api_key),
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
        sportsbook: Optional[Union[str, list[str]]] = None,
        add_sportsbook: Optional[Union[str, list[str]]] = None,
        sport: Optional[Union[str, list[str]]] = None,
        league: Optional[Union[str, list[str]]] = None,
        market: Optional[Union[str, list[str]]] = None,
        event: Optional[Union[str, list[str]]] = None,
        live: Optional[bool] = None,
        sort: Optional[str] = None,
        group_by: Optional[str] = None,
        fields: Optional[Union[str, list[str]]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
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
        sport: Optional[Union[str, list[str]]] = None,
        league: Optional[Union[str, list[str]]] = None,
        market: Optional[Union[str, list[str]]] = None,
        event: Optional[Union[str, list[str]]] = None,
        live: Optional[bool] = None,
        sportsbook: Optional[Union[str, list[str]]] = None,
        add_sportsbook: Optional[Union[str, list[str]]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
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
        market: Optional[str] = None,
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


class _EVResource:
    """Access +EV opportunities."""

    def __init__(self, client: SharpAPI):
        self._client = client

    def get(
        self,
        *,
        sport: Optional[Union[str, list[str]]] = None,
        league: Optional[Union[str, list[str]]] = None,
        sportsbook: Optional[Union[str, list[str]]] = None,
        add_sportsbook: Optional[Union[str, list[str]]] = None,
        market: Optional[Union[str, list[str]]] = None,
        min_ev: Optional[float] = None,
        max_ev: Optional[float] = None,
        min_market_width: Optional[float] = None,
        max_market_width: Optional[float] = None,
        max_odds_age: Optional[int] = None,
        date_range: Optional[str] = None,
        live: Optional[bool] = None,
        sort: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
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
        sport: Optional[Union[str, list[str]]] = None,
        league: Optional[Union[str, list[str]]] = None,
        sportsbook: Optional[Union[str, list[str]]] = None,
        add_sportsbook: Optional[Union[str, list[str]]] = None,
        market: Optional[Union[str, list[str]]] = None,
        min_profit: Optional[float] = None,
        max_odds_age: Optional[int] = None,
        live: Optional[bool] = None,
        sort: Optional[str] = None,
        group: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
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
        sport: Optional[Union[str, list[str]]] = None,
        league: Optional[Union[str, list[str]]] = None,
        min_profit: Optional[float] = None,
        limit: Optional[int] = None,
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
        sport: Optional[Union[str, list[str]]] = None,
        league: Optional[Union[str, list[str]]] = None,
        sportsbook: Optional[Union[str, list[str]]] = None,
        market: Optional[Union[str, list[str]]] = None,
        min_size: Optional[float] = None,
        max_odds_age: Optional[int] = None,
        live: Optional[bool] = None,
        state: Optional[str] = None,
        sort: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
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
        sport: Optional[Union[str, list[str]]] = None,
        league: Optional[Union[str, list[str]]] = None,
        sportsbook: Optional[Union[str, list[str]]] = None,
        market: Optional[Union[str, list[str]]] = None,
        max_hold: Optional[float] = None,
        live: Optional[bool] = None,
        state: Optional[str] = None,
        sort: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
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

    def list(self, *, sport: Optional[str] = None) -> APIResponse[list[League]]:
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
        sport: Optional[str] = None,
        league: Optional[Union[str, list[str]]] = None,
        live: Optional[bool] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
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
        sportsbook: Optional[Union[str, list[str]]] = None,
        league: Optional[Union[str, list[str]]] = None,
        sport: Optional[Union[str, list[str]]] = None,
        market: Optional[Union[str, list[str]]] = None,
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
        sportsbook: Optional[Union[str, list[str]]] = None,
        league: Optional[Union[str, list[str]]] = None,
        sport: Optional[Union[str, list[str]]] = None,
        market: Optional[Union[str, list[str]]] = None,
        min_ev: Optional[float] = None,
        min_profit: Optional[float] = None,
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
        sportsbook: Optional[Union[str, list[str]]] = None,
        league: Optional[Union[str, list[str]]] = None,
        sport: Optional[Union[str, list[str]]] = None,
        market: Optional[Union[str, list[str]]] = None,
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
        sportsbook: Optional[Union[str, list[str]]] = None,
        market: Optional[Union[str, list[str]]] = None,
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
