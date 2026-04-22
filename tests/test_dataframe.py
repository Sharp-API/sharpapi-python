"""Tests for pandas DataFrame integration."""

import pytest

from sharpapi._base import parse_response
from sharpapi.models import ArbitrageOpportunity, EVOpportunity

pd = pytest.importorskip("pandas")

from .conftest import ARBITRAGE_RESPONSE, EV_RESPONSE  # noqa: E402  (must follow importorskip)


class TestToDataFrame:
    def test_arbitrage_dataframe(self):
        result = parse_response(ARBITRAGE_RESPONSE, ArbitrageOpportunity)
        df = result.to_dataframe()
        assert len(df) == 1
        assert df.iloc[0]["profit_percent"] == 1.83
        assert df.iloc[0]["sport"] == "basketball"

    def test_ev_dataframe(self):
        result = parse_response(EV_RESPONSE, EVOpportunity)
        df = result.to_dataframe()
        assert len(df) == 1
        assert df.iloc[0]["ev_percentage"] == 4.2
        assert df.iloc[0]["sportsbook"] == "draftkings"

    def test_flattens_nested_dicts(self):
        result = parse_response(ARBITRAGE_RESPONSE, ArbitrageOpportunity)
        df = result.to_dataframe(flatten=True)
        assert "game_state_period" in df.columns
        assert "game_state_clock" in df.columns
        assert "game_state_score_home" in df.columns
        assert df.iloc[0]["game_state_period"] == "Q2"

    def test_no_flatten_keeps_nested(self):
        result = parse_response(ARBITRAGE_RESPONSE, ArbitrageOpportunity)
        df = result.to_dataframe(flatten=False)
        assert "game_state" in df.columns
        gs = df.iloc[0]["game_state"]
        assert gs["period"] == "Q2"

    def test_legs_remain_as_list(self):
        result = parse_response(ARBITRAGE_RESPONSE, ArbitrageOpportunity)
        df = result.to_dataframe()
        assert "legs" in df.columns
        legs = df.iloc[0]["legs"]
        assert isinstance(legs, list)
        assert len(legs) == 2

    def test_empty_response(self):
        result = parse_response({"data": []}, ArbitrageOpportunity)
        df = result.to_dataframe()
        assert df.empty

    def test_multiple_rows(self):
        multi = {
            "data": [
                {
                    "id": "ev_1", "sport": "basketball", "league": "nba",
                    "selection": "A", "sportsbook": "dk",
                    "odds_american": -110, "odds_decimal": 1.909,
                    "ev_percentage": 4.2, "possibly_stale": False, "warnings": [],
                },
                {
                    "id": "ev_2", "sport": "basketball", "league": "nba",
                    "selection": "B", "sportsbook": "fd",
                    "odds_american": 130, "odds_decimal": 2.3,
                    "ev_percentage": 2.8, "possibly_stale": False, "warnings": [],
                },
            ],
        }
        result = parse_response(multi, EVOpportunity)
        df = result.to_dataframe()
        assert len(df) == 2
        assert list(df["ev_percentage"]) == [4.2, 2.8]
        assert list(df["sportsbook"]) == ["dk", "fd"]

    def test_dataframe_dtypes(self):
        result = parse_response(EV_RESPONSE, EVOpportunity)
        df = result.to_dataframe()
        assert df["ev_percentage"].dtype == "float64"
        assert "str" in str(df["sportsbook"].dtype).lower() or df["sportsbook"].dtype == "object"
