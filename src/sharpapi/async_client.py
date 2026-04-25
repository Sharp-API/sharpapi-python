"""SharpAPI asynchronous Python client."""

from __future__ import annotations

import asyncio
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
    GameState,
    League,
    LowHoldOpportunity,
    Market,
    MiddleOpportunity,
    OddsLine,
    RateLimitInfo,
    Sport,
    Sportsbook,
)


class AsyncSharpAPI:
    """Async SharpAPI Python client.

    Provides typed access to odds, +EV, arbitrage, middles, and streaming
    endpoints using ``async``/``await``.

    Args:
        api_key: Your SharpAPI key (e.g. ``sk_live_...``).
        base_url: Override the API base URL (defaults to production).
        timeout: HTTP timeout in seconds.
        auth_method: How to send the API key on REST requests. ``"x-api-key"``
            (default) sends the ``X-API-Key`` header. ``"bearer"`` sends
            ``Authorization: Bearer <key>`` instead — useful when running
            behind IAM layers, SSO, or API gateways that strip custom
            headers. SSE streams (sync client only) always authenticate via
            ``?api_key=`` query and are unaffected.

    Example::

        import asyncio
        from sharpapi import AsyncSharpAPI

        async def main():
            async with AsyncSharpAPI("sk_live_xxx") as client:
                arbs = await client.arbitrage.get(min_profit=1.0)
                for arb in arbs.data:
                    print(f"{arb.profit_percent}% — {arb.event_name}")

            # Or, behind a proxy that requires standard Bearer auth:
            async with AsyncSharpAPI("sk_live_xxx", auth_method="bearer") as c:
                ...

        asyncio.run(main())
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
        self._http = httpx.AsyncClient(
            base_url=f"{self._base_url}/api/v1",
            headers=make_headers(api_key, auth_method),
            timeout=timeout,
        )
        self._last_rate_limit = RateLimitInfo()

        # Resource namespaces
        self.odds = _AsyncOddsResource(self)
        self.ev = _AsyncEVResource(self)
        self.arbitrage = _AsyncArbitrageResource(self)
        self.middles = _AsyncMiddlesResource(self)
        self.low_hold = _AsyncLowHoldResource(self)
        self.gamestate = _AsyncGameStateResource(self)
        self.sports = _AsyncSportsResource(self)
        self.leagues = _AsyncLeaguesResource(self)
        self.sportsbooks = _AsyncSportsbooksResource(self)
        self.events = _AsyncEventsResource(self)
        self.account = _AsyncAccountResource(self)
        self.keys = _AsyncKeysResource(self)

    @property
    def rate_limit(self) -> RateLimitInfo:
        """Rate limit info from the last request."""
        return self._last_rate_limit

    async def _request(self, method: str, path: str, params: dict | None = None, **kwargs) -> Any:
        """Make an async request, return parsed JSON. Retries 502/503/504 with jittered backoff."""
        if params:
            params = _clean_params(params)

        response: httpx.Response | None = None
        for attempt in range(1, RETRY_MAX_ATTEMPTS + 1):
            exc: Exception | None = None
            try:
                response = await self._http.request(method, path, params=params, **kwargs)
            except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError) as e:
                exc = e

            if attempt < RETRY_MAX_ATTEMPTS and should_retry(response, exc):
                await asyncio.sleep(retry_delay(attempt))
                continue
            if exc is not None:
                raise exc
            break

        assert response is not None
        self._last_rate_limit = parse_rate_limit(response)
        handle_errors(response)
        return response.json()

    async def _get(self, path: str, params: dict | None = None) -> Any:
        return await self._request("GET", path, params)

    async def _post(self, path: str, json_body: Any = None, params: dict | None = None) -> Any:
        return await self._request("POST", path, params, json=json_body)

    async def close(self) -> None:
        """Close the async HTTP client."""
        await self._http.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()


# =============================================================================
# Async Resource Namespaces
# =============================================================================


class _AsyncOddsResource:
    """Async access to odds data."""

    def __init__(self, client: AsyncSharpAPI):
        self._client = client

    async def get(
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
        """Get current odds snapshot."""
        data = await self._client._get("/odds", {
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
        return parse_response(data, OddsLine)

    async def best(
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
        data = await self._client._get("/odds/best", {
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
        return parse_response(data, OddsLine)

    async def comparison(
        self,
        event_id: str,
        *,
        market: str | None = None,
    ) -> APIResponse[list[OddsLine]]:
        """Get side-by-side odds comparison for an event."""
        data = await self._client._get("/odds/comparison", {
            "event_id": event_id,
            "market": market,
        })
        return parse_response(data, OddsLine)

    async def batch(self, event_ids: list[str]) -> APIResponse[list[OddsLine]]:
        """Batch odds lookup for multiple events."""
        data = await self._client._post("/odds/batch", {"event_ids": event_ids})
        return parse_response(data, OddsLine)

    async def closing(
        self,
        event_id: str,
        *,
        sportsbook: str | None = None,
    ) -> ClosingSnapshot:
        """Get closing-line snapshot for an event.

        Returns the captured closing odds grouped by sportsbook. If no
        closing data has been captured for the event, the returned
        ``ClosingSnapshot.books`` mapping will be empty.
        """
        data = await self._client._get("/odds/closing", {
            "event_id": event_id,
            "sportsbook": sportsbook or None,
        })
        raw = data.get("data", data)
        return ClosingSnapshot.model_validate(raw)


class _AsyncEVResource:
    """Async access to +EV opportunities."""

    def __init__(self, client: AsyncSharpAPI):
        self._client = client

    async def get(
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
        """Get +EV opportunities. Requires Pro tier or higher."""
        data = await self._client._get("/opportunities/ev", {
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
        return parse_response(data, EVOpportunity)


class _AsyncArbitrageResource:
    """Async access to arbitrage opportunities."""

    def __init__(self, client: AsyncSharpAPI):
        self._client = client

    async def get(
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
        """Get arbitrage opportunities. Requires Hobby tier or higher."""
        data = await self._client._get("/opportunities/arbitrage", {
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
        return parse_response(data, ArbitrageOpportunity)


class _AsyncMiddlesResource:
    """Async access to middle opportunities."""

    def __init__(self, client: AsyncSharpAPI):
        self._client = client

    async def get(
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
        """Get middle opportunities. Requires Pro tier or higher."""
        data = await self._client._get("/opportunities/middles", {
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
        return parse_response(data, MiddleOpportunity)


class _AsyncLowHoldResource:
    """Async access to low-hold opportunities."""

    def __init__(self, client: AsyncSharpAPI):
        self._client = client

    async def get(
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
        """Get low-hold opportunities."""
        data = await self._client._get("/opportunities/low_hold", {
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
        return parse_response(data, LowHoldOpportunity)


class _AsyncGameStateResource:
    """Async access to live game state — scores, period, clock —
    merged across sportsbooks.

    Requires the Game State add-on ($79/mo) or Enterprise tier.
    """

    def __init__(self, client: AsyncSharpAPI):
        self._client = client

    async def get(self, sport: str | None = None) -> dict[str, dict[str, GameState]]:
        """Fetch the current game state.

        Args:
            sport: Limit to a single sport (e.g. ``"basketball"``).
                Omit to fetch every sport at once.

        Returns:
            Nested mapping ``{sport: {event_id: GameState}}``.
        """
        path = f"/gamestate/{sport}" if sport else "/gamestate"
        data = await self._client._get(path)
        raw = data.get("data", {}) or {}
        result: dict[str, dict[str, GameState]] = {}
        for sport_key, events in raw.items():
            if not isinstance(events, dict):
                continue
            result[sport_key] = {
                eid: GameState.model_validate(state)
                for eid, state in events.items()
                if isinstance(state, dict)
            }
        return result


class _AsyncSportsResource:
    def __init__(self, client: AsyncSharpAPI):
        self._client = client

    async def list(self) -> APIResponse[list[Sport]]:
        """List all available sports."""
        data = await self._client._get("/sports")
        return parse_response(data, Sport)

    async def get(self, sport_id: str) -> Sport:
        """Get a specific sport."""
        data = await self._client._get(f"/sports/{sport_id}")
        raw = data.get("data", data)
        return Sport.model_validate(raw)


class _AsyncLeaguesResource:
    def __init__(self, client: AsyncSharpAPI):
        self._client = client

    async def list(self, *, sport: str | None = None) -> APIResponse[list[League]]:
        """List all leagues, optionally filtered by sport."""
        data = await self._client._get("/leagues", {"sport": sport})
        return parse_response(data, League)

    async def get(self, league_id: str) -> League:
        """Get a specific league."""
        data = await self._client._get(f"/leagues/{league_id}")
        raw = data.get("data", data)
        return League.model_validate(raw)


class _AsyncSportsbooksResource:
    def __init__(self, client: AsyncSharpAPI):
        self._client = client

    async def list(self) -> APIResponse[list[Sportsbook]]:
        """List all active sportsbooks."""
        data = await self._client._get("/sportsbooks")
        return parse_response(data, Sportsbook)

    async def get(self, book_id: str) -> Sportsbook:
        """Get a specific sportsbook."""
        data = await self._client._get(f"/sportsbooks/{book_id}")
        raw = data.get("data", data)
        return Sportsbook.model_validate(raw)


class _AsyncEventsResource:
    def __init__(self, client: AsyncSharpAPI):
        self._client = client

    async def list(
        self,
        *,
        sport: str | None = None,
        league: str | list[str] | None = None,
        live: bool | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> APIResponse[list[Event]]:
        """List events."""
        data = await self._client._get("/events", {
            "sport": sport,
            "league": league,
            "live": live,
            "limit": limit,
            "offset": offset,
        })
        return parse_response(data, Event)

    async def get(self, event_id: str) -> Event:
        """Get a specific event."""
        data = await self._client._get(f"/events/{event_id}")
        raw = data.get("data", data)
        return Event.model_validate(raw)

    async def markets(self, event_id: str) -> APIResponse[list[Market]]:
        """List the markets available on a specific event."""
        data = await self._client._get(f"/events/{event_id}/markets")
        return parse_response(data, Market)


class _AsyncAccountResource:
    def __init__(self, client: AsyncSharpAPI):
        self._client = client

    async def me(self) -> AccountInfo:
        """Get current account info (tier, limits, features)."""
        data = await self._client._get("/account")
        raw = data.get("data", data)
        return AccountInfo.model_validate(raw)

    async def usage(self) -> dict:
        """Get current usage stats."""
        data = await self._client._get("/account/usage")
        return data.get("data", data)


class _AsyncKeysResource:
    """Async access to API key CRUD on the current account."""

    def __init__(self, client: AsyncSharpAPI):
        self._client = client

    async def list(self) -> APIResponse[list[APIKey]]:
        """List all API keys on the account."""
        data = await self._client._get("/account/keys")
        return parse_response(data, APIKey)

    async def create(self, name: str) -> APIKey:
        """Create a new API key. Returned ``APIKey.key`` is shown only once."""
        data = await self._client._post("/account/keys", {"name": name})
        raw = data.get("data", data)
        return APIKey.model_validate(raw)

    async def revoke(self, key_id: str) -> None:
        """Revoke (delete) an API key by ID."""
        await self._client._request("DELETE", f"/account/keys/{key_id}")

    async def rotate(self, key_id: str) -> APIKey:
        """Rotate an API key — issues a new key and revokes the old one."""
        data = await self._client._post(f"/account/keys/{key_id}/rotate")
        raw = data.get("data", data)
        if isinstance(raw, dict) and "new_key" in raw:
            return APIKey.model_validate(raw["new_key"])
        return APIKey.model_validate(raw)
