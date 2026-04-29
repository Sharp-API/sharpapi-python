"""Tests for Pydantic response model parsing."""

from sharpapi._base import parse_response
from sharpapi.models import (
    ArbitrageOpportunity,
    EVOpportunity,
    LowHoldOpportunity,
    MiddleOpportunity,
    OddsLine,
    Sport,
)

from .conftest import (
    ARBITRAGE_RESPONSE,
    EV_RESPONSE,
    LOW_HOLD_RESPONSE,
    MIDDLES_RESPONSE,
    ODDS_RESPONSE,
    SPORTS_RESPONSE,
)


class TestArbitrageModel:
    def test_parse_full_response(self):
        result = parse_response(ARBITRAGE_RESPONSE, ArbitrageOpportunity)
        assert len(result.data) == 1
        arb = result.data[0]
        assert arb.id == "arb_dk_pin_nba_lal_bos_ml"
        assert arb.profit_percent == 1.83
        assert arb.implied_total == 98.2
        assert arb.sport == "basketball"
        assert arb.league == "nba"
        assert arb.is_live is True
        assert arb.possibly_stale is False
        assert arb.warnings == ["LIVE_GAME"]

    def test_legs(self):
        result = parse_response(ARBITRAGE_RESPONSE, ArbitrageOpportunity)
        arb = result.data[0]
        assert len(arb.legs) == 2
        leg1 = arb.legs[0]
        assert leg1.sportsbook == "draftkings"
        assert leg1.selection == "Los Angeles Lakers"
        assert leg1.odds_american == 145
        assert leg1.odds_decimal == 2.45
        assert leg1.stake_percent == 41.5
        assert leg1.external_event_id == "dk_12345"

    def test_ev_cross_reference(self):
        result = parse_response(ARBITRAGE_RESPONSE, ArbitrageOpportunity)
        arb = result.data[0]
        assert arb.ev_available is True
        assert arb.ev_percentage == 3.2

    def test_meta(self):
        result = parse_response(ARBITRAGE_RESPONSE, ArbitrageOpportunity)
        assert result.meta is not None
        assert result.meta.pagination is not None
        assert result.meta.count == 1
        assert result.meta.pagination.limit == 50
        assert result.meta.pagination.has_more is False


class TestEVModel:
    def test_parse_full_response(self):
        result = parse_response(EV_RESPONSE, EVOpportunity)
        assert len(result.data) == 1
        ev = result.data[0]
        assert ev.ev_percentage == 4.2
        assert ev.selection == "PHO Suns"
        assert ev.sportsbook == "draftkings"
        assert ev.odds_american == -105
        assert ev.odds_decimal == 1.952

    def test_sharp_reference(self):
        result = parse_response(EV_RESPONSE, EVOpportunity)
        ev = result.data[0]
        assert ev.devig_method == "power"
        assert ev.sharp_book == "pinnacle"
        assert ev.no_vig_odds == 1.912
        assert ev.fair_probability == 0.523

    def test_scoring(self):
        result = parse_response(EV_RESPONSE, EVOpportunity)
        ev = result.data[0]
        assert ev.confidence_score == 87
        assert ev.kelly_percent == 0.021
        assert ev.book_count == 8

    def test_aliased_fields(self):
        result = parse_response(EV_RESPONSE, EVOpportunity)
        ev = result.data[0]
        # game_id -> event_id, game -> event_name, market -> market_type
        assert ev.event_id == "evt_123"
        assert ev.event_name == "PHI 76ers vs PHO Suns"
        assert ev.market_type == "moneyline"


class TestMiddlesModel:
    def test_parse_full_response(self):
        result = parse_response(MIDDLES_RESPONSE, MiddleOpportunity)
        assert len(result.data) == 1
        mid = result.data[0]
        assert mid.event_name == "Buffalo Bills @ Kansas City Chiefs"
        assert mid.middle_size == 5.0
        assert mid.middle_numbers == [3, 4, 5, 6, 7]
        assert mid.middle_probability == 0.377
        assert mid.quality_score == 85

    def test_sides(self):
        result = parse_response(MIDDLES_RESPONSE, MiddleOpportunity)
        mid = result.data[0]
        assert mid.side1.book == "draftkings"
        assert mid.side1.line == -2.5
        assert mid.side1.odds.american == -110
        assert mid.side2.book == "fanduel"
        assert mid.side2.line == 7.5

    def test_key_numbers(self):
        result = parse_response(MIDDLES_RESPONSE, MiddleOpportunity)
        mid = result.data[0]
        assert mid.key_numbers == [3, 7]


class TestLowHoldModel:
    def test_parse_response(self):
        result = parse_response(LOW_HOLD_RESPONSE, LowHoldOpportunity)
        assert len(result.data) == 1
        lh = result.data[0]
        assert lh.hold_percentage == 1.8
        assert lh.sport == "basketball"


class TestOddsLineModel:
    def test_parse_response(self):
        result = parse_response(ODDS_RESPONSE, OddsLine)
        assert len(result.data) == 1
        line = result.data[0]
        assert line.sportsbook == "draftkings"
        assert line.odds_american == 145
        assert line.odds_decimal == 2.45
        assert line.probability == 0.408
        assert line.home_team == "Boston Celtics"
        assert line.away_team == "Los Angeles Lakers"
        assert line.is_live is False


class TestSportModel:
    def test_parse_response(self):
        result = parse_response(SPORTS_RESPONSE, Sport)
        assert len(result.data) == 2
        assert result.data[0].name == "Basketball"
        assert result.data[1].slug == "football"


class TestEmptyResponse:
    def test_empty_data_array(self):
        result = parse_response({"data": []}, ArbitrageOpportunity)
        assert result.data == []
        assert result.meta is None

    def test_missing_optional_fields(self):
        minimal = {
            "data": [{
                "id": "arb_min",
                "event_name": "A vs B",
                "sport": "basketball",
                "market_type": "moneyline",
                "profit_percent": 0.5,
                "legs": [
                    {"sportsbook": "dk", "selection": "A", "odds_american": 100,
                     "odds_decimal": 2.0, "stake_percent": 50.0},
                    {"sportsbook": "fd", "selection": "B", "odds_american": 100,
                     "odds_decimal": 2.0, "stake_percent": 50.0},
                ],
            }],
        }
        result = parse_response(minimal, ArbitrageOpportunity)
        arb = result.data[0]
        assert arb.warnings == []
        assert arb.possibly_stale is False
        assert arb.is_player_prop is False
