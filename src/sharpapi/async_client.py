"""SharpAPI asynchronous Python client."""

from __future__ import annotations

from typing import Any, Optional, Union

import httpx

from ._base import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    handle_errors,
    make_headers,
    parse_rate_limit,
    parse_response,
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


class AsyncSharpAPI:
    """Async SharpAPI Python client.

    Provides typed access to odds, +EV, arbitrage, middles, and streaming
    endpoints using ``async``/``await``.

    Example::

        import asyncio
        from sharpapi import AsyncSharpAPI

        async def main():
            async with AsyncSharpAPI("sk_live_xxx") as client:
                arbs = await client.arbitrage.get(min_profit=1.0)
                for arb in arbs.data:
                    print(f"{arb.profit_percent}% — {arb.event_name}")

        asyncio.run(main())
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
        self._http = httpx.AsyncClient(
            base_url=f"{self._base_url}/api/v1",
            headers=make_headers(api_key),
            timeout=timeout,
        )
        self._last_rate_limit = RateLimitInfo()

        # Resource namespaces
        self.odds = _AsyncOddsResource(self)
        self.ev = _AsyncEVResource(self)
        self.arbitrage = _AsyncArbitrageResource(self)
        self.middles = _AsyncMiddlesResource(self)
        self.low_hold = _AsyncLowHoldResource(self)
        self.sports = _AsyncSportsResource(self)
        self.leagues = _AsyncLeaguesResource(self)
        self.sportsbooks = _AsyncSportsbooksResource(self)
        self.events = _AsyncEventsResource(self)
        self.account = _AsyncAccountResource(self)

    @property
    def rate_limit(self) -> RateLimitInfo:
        """Rate limit info from the last request."""
        return self._last_rate_limit

    async def _request(self, method: str, path: str, params: dict | None = None, **kwargs) -> Any:
        """Make an async API request and return parsed JSON."""
        if params:
            params = _clean_params(params)

        response = await self._http.request(method, path, params=params, **kwargs)
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
        market: Optional[str] = None,
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


class _AsyncEVResource:
    """Async access to +EV opportunities."""

    def __init__(self, client: AsyncSharpAPI):
        self._client = client

    async def get(
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

    async def list(self, *, sport: Optional[str] = None) -> APIResponse[list[League]]:
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
        sport: Optional[str] = None,
        league: Optional[Union[str, list[str]]] = None,
        live: Optional[bool] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
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

    async def search(self, query: str) -> APIResponse[list[Event]]:
        """Search events by name."""
        data = await self._client._get("/events/search", {"q": query})
        return parse_response(data, Event)


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
