"""Tests for the asynchronous AsyncSharpAPI client."""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from sharpapi import (
    ArbitrageOpportunity,
    AsyncSharpAPI,
    AuthenticationError,
    EVOpportunity,
    OddsLine,
    RateLimitedError,
    Sport,
)
from .conftest import (
    API_KEY,
    ARBITRAGE_RESPONSE,
    BASE_URL,
    ERROR_401,
    ERROR_429,
    EV_RESPONSE,
    ODDS_RESPONSE,
    RATE_LIMIT_HEADERS,
    SPORTS_RESPONSE,
    ACCOUNT_RESPONSE,
)


# =============================================================================
# Async Client Lifecycle
# =============================================================================


class TestAsyncClientInit:
    def test_requires_api_key(self):
        with pytest.raises(ValueError, match="api_key is required"):
            AsyncSharpAPI("")

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        async with AsyncSharpAPI("sk_test_123") as client:
            assert client._api_key == "sk_test_123"

    def test_resource_namespaces_exist(self):
        client = AsyncSharpAPI("sk_test_123")
        assert hasattr(client, "odds")
        assert hasattr(client, "ev")
        assert hasattr(client, "arbitrage")
        assert hasattr(client, "middles")
        assert hasattr(client, "low_hold")
        assert hasattr(client, "sports")
        assert hasattr(client, "leagues")
        assert hasattr(client, "sportsbooks")
        assert hasattr(client, "events")
        assert hasattr(client, "account")
        # No stream on async (SSE uses sync httpx streaming)
        assert not hasattr(client, "stream")


# =============================================================================
# Async Error Handling
# =============================================================================


class TestAsyncErrors:
    @pytest.mark.asyncio
    @respx.mock
    async def test_401_raises_auth_error(self):
        respx.get(f"{BASE_URL}/api/v1/odds").mock(
            return_value=Response(401, json=ERROR_401)
        )
        async with AsyncSharpAPI(API_KEY) as client:
            with pytest.raises(AuthenticationError) as exc_info:
                await client.odds.get()
            assert exc_info.value.status == 401

    @pytest.mark.asyncio
    @respx.mock
    async def test_429_raises_rate_limited(self):
        respx.get(f"{BASE_URL}/api/v1/odds").mock(
            return_value=Response(429, json=ERROR_429)
        )
        async with AsyncSharpAPI(API_KEY) as client:
            with pytest.raises(RateLimitedError) as exc_info:
                await client.odds.get()
            assert exc_info.value.retry_after == 30


# =============================================================================
# Async Rate Limiting
# =============================================================================


class TestAsyncRateLimiting:
    @pytest.mark.asyncio
    @respx.mock
    async def test_rate_limit_parsed(self):
        respx.get(f"{BASE_URL}/api/v1/odds").mock(
            return_value=Response(200, json=ODDS_RESPONSE, headers=RATE_LIMIT_HEADERS)
        )
        async with AsyncSharpAPI(API_KEY) as client:
            await client.odds.get()
            assert client.rate_limit.limit == 300
            assert client.rate_limit.remaining == 297
            assert client.rate_limit.tier == "pro"


# =============================================================================
# Async Odds
# =============================================================================


class TestAsyncOdds:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_odds(self):
        respx.get(f"{BASE_URL}/api/v1/odds").mock(
            return_value=Response(200, json=ODDS_RESPONSE)
        )
        async with AsyncSharpAPI(API_KEY) as client:
            result = await client.odds.get(league="nba")
            assert len(result.data) == 1
            assert isinstance(result.data[0], OddsLine)

    @pytest.mark.asyncio
    @respx.mock
    async def test_best_odds(self):
        respx.get(f"{BASE_URL}/api/v1/odds/best").mock(
            return_value=Response(200, json=ODDS_RESPONSE)
        )
        async with AsyncSharpAPI(API_KEY) as client:
            result = await client.odds.best(league="nba")
            assert len(result.data) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_batch_odds(self):
        respx.post(f"{BASE_URL}/api/v1/odds/batch").mock(
            return_value=Response(200, json=ODDS_RESPONSE)
        )
        async with AsyncSharpAPI(API_KEY) as client:
            result = await client.odds.batch(["evt_1"])
            assert len(result.data) == 1


# =============================================================================
# Async Opportunities
# =============================================================================


class TestAsyncOpportunities:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_arbitrage(self):
        respx.get(f"{BASE_URL}/api/v1/opportunities/arbitrage").mock(
            return_value=Response(200, json=ARBITRAGE_RESPONSE)
        )
        async with AsyncSharpAPI(API_KEY) as client:
            result = await client.arbitrage.get(min_profit=1.0)
            assert len(result.data) == 1
            assert isinstance(result.data[0], ArbitrageOpportunity)
            assert result.data[0].profit_percent == 1.83

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_ev(self):
        respx.get(f"{BASE_URL}/api/v1/opportunities/ev").mock(
            return_value=Response(200, json=EV_RESPONSE)
        )
        async with AsyncSharpAPI(API_KEY) as client:
            result = await client.ev.get(min_ev=3.0)
            assert len(result.data) == 1
            assert isinstance(result.data[0], EVOpportunity)
            assert result.data[0].ev_percentage == 4.2


# =============================================================================
# Async Reference Data
# =============================================================================


class TestAsyncReferenceData:
    @pytest.mark.asyncio
    @respx.mock
    async def test_sports_list(self):
        respx.get(f"{BASE_URL}/api/v1/sports").mock(
            return_value=Response(200, json=SPORTS_RESPONSE)
        )
        async with AsyncSharpAPI(API_KEY) as client:
            result = await client.sports.list()
            assert len(result.data) == 2
            assert isinstance(result.data[0], Sport)

    @pytest.mark.asyncio
    @respx.mock
    async def test_account_me(self):
        respx.get(f"{BASE_URL}/api/v1/account").mock(
            return_value=Response(200, json=ACCOUNT_RESPONSE)
        )
        async with AsyncSharpAPI(API_KEY) as client:
            info = await client.account.me()
            assert info.key["tier"] == "pro"
            assert info.features.ev is True


# =============================================================================
# Async Auth Header
# =============================================================================


class TestAsyncAuthHeader:
    @pytest.mark.asyncio
    @respx.mock
    async def test_api_key_header_sent(self):
        route = respx.get(f"{BASE_URL}/api/v1/sports").mock(
            return_value=Response(200, json=SPORTS_RESPONSE)
        )
        async with AsyncSharpAPI(API_KEY) as client:
            await client.sports.list()
            assert route.calls[0].request.headers["x-api-key"] == API_KEY
