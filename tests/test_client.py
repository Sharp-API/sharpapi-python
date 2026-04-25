"""Tests for the synchronous SharpAPI client."""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from sharpapi import (
    ArbitrageOpportunity,
    AuthenticationError,
    EVOpportunity,
    GameState,
    LowHoldOpportunity,
    MiddleOpportunity,
    OddsLine,
    RateLimitedError,
    SharpAPI,
    SharpAPIError,
    Sport,
    TierRestrictedError,
    ValidationError,
)

from .conftest import (
    ACCOUNT_RESPONSE,
    API_KEY,
    ARBITRAGE_RESPONSE,
    BASE_URL,
    ERROR_400,
    ERROR_401,
    ERROR_403,
    ERROR_429,
    EV_RESPONSE,
    EVENTS_RESPONSE,
    GAMESTATE_BASKETBALL_RESPONSE,
    GAMESTATE_RESPONSE,
    LEAGUES_RESPONSE,
    LOW_HOLD_RESPONSE,
    MIDDLES_RESPONSE,
    ODDS_RESPONSE,
    RATE_LIMIT_HEADERS,
    SPORTS_RESPONSE,
    SPORTSBOOKS_RESPONSE,
)

# =============================================================================
# Client Lifecycle
# =============================================================================


class TestClientInit:
    def test_requires_api_key(self):
        with pytest.raises(ValueError, match="api_key is required"):
            SharpAPI("")

    def test_default_base_url(self):
        client = SharpAPI("sk_test_123")
        assert client._base_url == "https://api.sharpapi.io"
        client.close()

    def test_custom_base_url(self):
        client = SharpAPI("sk_test_123", base_url="https://custom.api.io/")
        assert client._base_url == "https://custom.api.io"
        client.close()

    def test_context_manager(self):
        with SharpAPI("sk_test_123") as client:
            assert client._api_key == "sk_test_123"

    def test_resource_namespaces_exist(self):
        client = SharpAPI("sk_test_123")
        assert hasattr(client, "odds")
        assert hasattr(client, "ev")
        assert hasattr(client, "arbitrage")
        assert hasattr(client, "middles")
        assert hasattr(client, "low_hold")
        assert hasattr(client, "gamestate")
        assert hasattr(client, "sports")
        assert hasattr(client, "leagues")
        assert hasattr(client, "sportsbooks")
        assert hasattr(client, "events")
        assert hasattr(client, "account")
        assert hasattr(client, "stream")
        client.close()


# =============================================================================
# Error Handling
# =============================================================================


class TestErrorHandling:
    @respx.mock
    def test_401_raises_authentication_error(self):
        respx.get(f"{BASE_URL}/api/v1/odds").mock(
            return_value=Response(401, json=ERROR_401)
        )
        with SharpAPI(API_KEY) as client:
            with pytest.raises(AuthenticationError) as exc_info:
                client.odds.get()
            assert exc_info.value.code == "invalid_api_key"
            assert exc_info.value.status == 401

    @respx.mock
    def test_403_raises_tier_restricted(self):
        respx.get(f"{BASE_URL}/api/v1/opportunities/ev").mock(
            return_value=Response(403, json=ERROR_403)
        )
        with SharpAPI(API_KEY) as client:
            with pytest.raises(TierRestrictedError) as exc_info:
                client.ev.get()
            assert exc_info.value.required_tier == "pro"

    @respx.mock
    def test_429_raises_rate_limited(self):
        respx.get(f"{BASE_URL}/api/v1/odds").mock(
            return_value=Response(429, json=ERROR_429)
        )
        with SharpAPI(API_KEY) as client:
            with pytest.raises(RateLimitedError) as exc_info:
                client.odds.get()
            assert exc_info.value.retry_after == 30

    @respx.mock
    def test_400_raises_validation_error(self):
        respx.get(f"{BASE_URL}/api/v1/opportunities/ev").mock(
            return_value=Response(400, json=ERROR_400)
        )
        with SharpAPI(API_KEY) as client:
            with pytest.raises(ValidationError):
                client.ev.get()

    @respx.mock
    def test_500_raises_generic_error(self):
        respx.get(f"{BASE_URL}/api/v1/odds").mock(
            return_value=Response(500, json={"error": {"message": "Internal error"}})
        )
        with SharpAPI(API_KEY) as client:
            with pytest.raises(SharpAPIError) as exc_info:
                client.odds.get()
            assert exc_info.value.status == 500


# =============================================================================
# Rate Limiting
# =============================================================================


class TestRateLimiting:
    @respx.mock
    def test_rate_limit_parsed_from_headers(self):
        respx.get(f"{BASE_URL}/api/v1/odds").mock(
            return_value=Response(200, json=ODDS_RESPONSE, headers=RATE_LIMIT_HEADERS)
        )
        with SharpAPI(API_KEY) as client:
            client.odds.get()
            rl = client.rate_limit
            assert rl.limit == 300
            assert rl.remaining == 297
            assert rl.reset == 1707401000.0
            assert rl.tier == "pro"

    @respx.mock
    def test_rate_limit_missing_headers(self):
        respx.get(f"{BASE_URL}/api/v1/odds").mock(
            return_value=Response(200, json=ODDS_RESPONSE)
        )
        with SharpAPI(API_KEY) as client:
            client.odds.get()
            rl = client.rate_limit
            assert rl.limit is None
            assert rl.remaining is None


# =============================================================================
# Odds Resource
# =============================================================================


class TestOddsResource:
    @respx.mock
    def test_get_odds(self):
        route = respx.get(f"{BASE_URL}/api/v1/odds").mock(
            return_value=Response(200, json=ODDS_RESPONSE)
        )
        with SharpAPI(API_KEY) as client:
            result = client.odds.get(league="nba", limit=10)
            assert len(result.data) == 1
            assert isinstance(result.data[0], OddsLine)
            assert result.data[0].sportsbook == "draftkings"
            # Verify query params sent
            assert "league=nba" in str(route.calls[0].request.url)
            assert "limit=10" in str(route.calls[0].request.url)

    @respx.mock
    def test_get_best_odds(self):
        respx.get(f"{BASE_URL}/api/v1/odds/best").mock(
            return_value=Response(200, json=ODDS_RESPONSE)
        )
        with SharpAPI(API_KEY) as client:
            result = client.odds.best(league="nba")
            assert len(result.data) == 1

    @respx.mock
    def test_odds_comparison(self):
        respx.get(f"{BASE_URL}/api/v1/odds/comparison").mock(
            return_value=Response(200, json=ODDS_RESPONSE)
        )
        with SharpAPI(API_KEY) as client:
            result = client.odds.comparison("evt_123")
            assert len(result.data) == 1

    @respx.mock
    def test_odds_batch(self):
        respx.post(f"{BASE_URL}/api/v1/odds/batch").mock(
            return_value=Response(200, json=ODDS_RESPONSE)
        )
        with SharpAPI(API_KEY) as client:
            result = client.odds.batch(["evt_1", "evt_2"])
            assert len(result.data) == 1


# =============================================================================
# Opportunity Resources
# =============================================================================


class TestArbitrageResource:
    @respx.mock
    def test_get_arbitrage(self):
        route = respx.get(f"{BASE_URL}/api/v1/opportunities/arbitrage").mock(
            return_value=Response(200, json=ARBITRAGE_RESPONSE)
        )
        with SharpAPI(API_KEY) as client:
            result = client.arbitrage.get(min_profit=1.0, sport="basketball")
            assert len(result.data) == 1
            arb = result.data[0]
            assert isinstance(arb, ArbitrageOpportunity)
            assert arb.profit_percent == 1.83
            assert len(arb.legs) == 2
            assert "min_profit=1.0" in str(route.calls[0].request.url)

    @respx.mock
    def test_arbitrage_with_list_params(self):
        route = respx.get(f"{BASE_URL}/api/v1/opportunities/arbitrage").mock(
            return_value=Response(200, json=ARBITRAGE_RESPONSE)
        )
        with SharpAPI(API_KEY) as client:
            client.arbitrage.get(sportsbook=["draftkings", "fanduel"])
            url = str(route.calls[0].request.url)
            assert (
                "sportsbook=draftkings%2Cfanduel" in url
                or "sportsbook=draftkings,fanduel" in url
            )


class TestEVResource:
    @respx.mock
    def test_get_ev(self):
        respx.get(f"{BASE_URL}/api/v1/opportunities/ev").mock(
            return_value=Response(200, json=EV_RESPONSE)
        )
        with SharpAPI(API_KEY) as client:
            result = client.ev.get(min_ev=3.0)
            assert len(result.data) == 1
            ev = result.data[0]
            assert isinstance(ev, EVOpportunity)
            assert ev.ev_percentage == 4.2
            assert ev.kelly_percent == 0.021


class TestMiddlesResource:
    @respx.mock
    def test_get_middles(self):
        respx.get(f"{BASE_URL}/api/v1/opportunities/middles").mock(
            return_value=Response(200, json=MIDDLES_RESPONSE)
        )
        with SharpAPI(API_KEY) as client:
            result = client.middles.get(sport="football")
            assert len(result.data) == 1
            mid = result.data[0]
            assert isinstance(mid, MiddleOpportunity)
            assert mid.middle_size == 5.0


class TestLowHoldResource:
    @respx.mock
    def test_get_low_hold(self):
        respx.get(f"{BASE_URL}/api/v1/opportunities/low_hold").mock(
            return_value=Response(200, json=LOW_HOLD_RESPONSE)
        )
        with SharpAPI(API_KEY) as client:
            result = client.low_hold.get(max_hold=2.0)
            assert len(result.data) == 1
            lh = result.data[0]
            assert isinstance(lh, LowHoldOpportunity)
            assert lh.hold_percentage == 1.8


class TestGameStateResource:
    @respx.mock
    def test_get_all_sports(self):
        respx.get(f"{BASE_URL}/api/v1/gamestate").mock(
            return_value=Response(200, json=GAMESTATE_RESPONSE)
        )
        with SharpAPI(API_KEY) as client:
            result = client.gamestate.get()
            assert set(result.keys()) == {"basketball", "football"}
            state = result["basketball"]["evt_lal_bos"]
            assert isinstance(state, GameState)
            assert state.home_score == 48
            assert state.away_score == 52
            assert state.game_period == "Q2"
            assert state.game_clock == "5:23"
            assert state.primary_book == "draftkings"
            assert state.book_count == 4
            assert state.stale is False
            # aggregator_stale defaults to False when omitted
            assert state.aggregator_stale is False

    @respx.mock
    def test_get_single_sport(self):
        route = respx.get(f"{BASE_URL}/api/v1/gamestate/basketball").mock(
            return_value=Response(200, json=GAMESTATE_BASKETBALL_RESPONSE)
        )
        with SharpAPI(API_KEY) as client:
            result = client.gamestate.get("basketball")
            assert route.called
            assert "football" not in result
            assert "evt_lal_bos" in result["basketball"]

    @respx.mock
    def test_aggregator_stale_passthrough(self):
        respx.get(f"{BASE_URL}/api/v1/gamestate").mock(
            return_value=Response(200, json=GAMESTATE_RESPONSE)
        )
        with SharpAPI(API_KEY) as client:
            result = client.gamestate.get()
            stale_state = result["basketball"]["evt_gsw_phx"]
            assert stale_state.aggregator_stale is True

    @respx.mock
    def test_unknown_extra_fields_pass_through(self):
        # Forward-compat: aggregator may add new fields the SDK doesn't know.
        respx.get(f"{BASE_URL}/api/v1/gamestate/basketball").mock(
            return_value=Response(200, json={
                "data": {
                    "basketball": {
                        "evt_x": {
                            "home_score": 0,
                            "away_score": 0,
                            "future_field": "experimental",
                        },
                    },
                },
                "updated_at": "2026-04-25T20:30:00Z",
            })
        )
        with SharpAPI(API_KEY) as client:
            result = client.gamestate.get("basketball")
            state = result["basketball"]["evt_x"]
            # Pydantic model_dump should include the unknown field thanks to
            # extra="allow".
            dumped = state.model_dump()
            assert dumped["future_field"] == "experimental"


# =============================================================================
# Reference Data Resources
# =============================================================================


class TestReferenceResources:
    @respx.mock
    def test_sports_list(self):
        respx.get(f"{BASE_URL}/api/v1/sports").mock(
            return_value=Response(200, json=SPORTS_RESPONSE)
        )
        with SharpAPI(API_KEY) as client:
            result = client.sports.list()
            assert len(result.data) == 2
            assert isinstance(result.data[0], Sport)

    @respx.mock
    def test_sports_get(self):
        respx.get(f"{BASE_URL}/api/v1/sports/basketball").mock(
            return_value=Response(200, json={
                "data": {
                    "id": "basketball",
                    "name": "Basketball",
                    "slug": "basketball",
                    "active": True,
                }
            })
        )
        with SharpAPI(API_KEY) as client:
            sport = client.sports.get("basketball")
            assert sport.name == "Basketball"

    @respx.mock
    def test_leagues_list(self):
        respx.get(f"{BASE_URL}/api/v1/leagues").mock(
            return_value=Response(200, json=LEAGUES_RESPONSE)
        )
        with SharpAPI(API_KEY) as client:
            result = client.leagues.list()
            assert len(result.data) == 2

    @respx.mock
    def test_sportsbooks_list(self):
        respx.get(f"{BASE_URL}/api/v1/sportsbooks").mock(
            return_value=Response(200, json=SPORTSBOOKS_RESPONSE)
        )
        with SharpAPI(API_KEY) as client:
            result = client.sportsbooks.list()
            assert result.data[0].id == "draftkings"

    @respx.mock
    def test_events_list(self):
        respx.get(f"{BASE_URL}/api/v1/events").mock(
            return_value=Response(200, json=EVENTS_RESPONSE)
        )
        with SharpAPI(API_KEY) as client:
            result = client.events.list(league="nba")
            assert len(result.data) == 1

    @respx.mock
    def test_account_me(self):
        respx.get(f"{BASE_URL}/api/v1/account").mock(
            return_value=Response(200, json=ACCOUNT_RESPONSE)
        )
        with SharpAPI(API_KEY) as client:
            info = client.account.me()
            assert info.key is not None
            assert info.limits is not None
            assert info.features is not None
            assert info.key["tier"] == "pro"
            assert info.limits.requests_per_minute == 300
            assert info.features.ev is True


# =============================================================================
# Auth Header
# =============================================================================


class TestAuthHeader:
    @respx.mock
    def test_api_key_header_sent(self):
        route = respx.get(f"{BASE_URL}/api/v1/sports").mock(
            return_value=Response(200, json=SPORTS_RESPONSE)
        )
        with SharpAPI(API_KEY) as client:
            client.sports.list()
            assert route.calls[0].request.headers["x-api-key"] == API_KEY
            # Bearer must NOT be sent in the default mode.
            assert "authorization" not in route.calls[0].request.headers

    @respx.mock
    def test_bearer_auth_method_sends_authorization(self):
        route = respx.get(f"{BASE_URL}/api/v1/sports").mock(
            return_value=Response(200, json=SPORTS_RESPONSE)
        )
        with SharpAPI(API_KEY, auth_method="bearer") as client:
            client.sports.list()
            req = route.calls[0].request
            assert req.headers["authorization"] == f"Bearer {API_KEY}"
            # X-API-Key must NOT be sent in bearer mode.
            assert "x-api-key" not in req.headers

    @respx.mock
    def test_user_agent_sent(self):
        route = respx.get(f"{BASE_URL}/api/v1/sports").mock(
            return_value=Response(200, json=SPORTS_RESPONSE)
        )
        with SharpAPI(API_KEY) as client:
            client.sports.list()
            assert "sharpapi-python" in route.calls[0].request.headers["user-agent"]
