"""Tests for odds conversion utilities and param cleaning."""

from sharpapi._utils import (
    _clean_params,
    american_to_decimal,
    american_to_probability,
    decimal_to_american,
)


class TestAmericanToDecimal:
    def test_negative_odds(self):
        assert round(american_to_decimal(-110), 3) == 1.909

    def test_positive_odds(self):
        assert american_to_decimal(150) == 2.5

    def test_even_money(self):
        assert american_to_decimal(100) == 2.0

    def test_heavy_favorite(self):
        assert round(american_to_decimal(-500), 3) == 1.2

    def test_long_shot(self):
        assert american_to_decimal(1000) == 11.0


class TestDecimalToAmerican:
    def test_underdog(self):
        assert decimal_to_american(2.5) == 150

    def test_favorite(self):
        assert decimal_to_american(1.909) == -110

    def test_even_money(self):
        assert decimal_to_american(2.0) == 100

    def test_heavy_favorite(self):
        assert decimal_to_american(1.2) == -500


class TestAmericanToProbability:
    def test_favorite(self):
        assert round(american_to_probability(-110), 3) == 0.524

    def test_underdog(self):
        assert round(american_to_probability(150), 3) == 0.4

    def test_even_money(self):
        assert american_to_probability(100) == 0.5

    def test_heavy_favorite(self):
        prob = american_to_probability(-500)
        assert round(prob, 4) == 0.8333


class TestCleanParams:
    def test_removes_none_values(self):
        assert _clean_params({"a": 1, "b": None, "c": "x"}) == {"a": 1, "c": "x"}

    def test_joins_lists(self):
        assert _clean_params({"sport": ["nba", "nfl"]}) == {"sport": "nba,nfl"}

    def test_converts_booleans(self):
        assert _clean_params({"live": True}) == {"live": "true"}
        assert _clean_params({"live": False}) == {"live": "false"}

    def test_empty_dict(self):
        assert _clean_params({}) == {}

    def test_all_none(self):
        assert _clean_params({"a": None, "b": None}) == {}

    def test_preserves_numbers(self):
        assert _clean_params({"min_ev": 3.5, "limit": 50}) == {"min_ev": 3.5, "limit": 50}
