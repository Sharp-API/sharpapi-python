import json
from pathlib import Path

import pytest

from sharpapi import models as M
from sharpapi._base import parse_response

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "live-api"


LIVE_MODEL_FIXTURES = [
    ("live-odds.json", M.OddsLine),
    ("live-ev.json", M.EVOpportunity),
    ("live-arb.json", M.ArbitrageOpportunity),
    ("live-middles.json", M.MiddleOpportunity),
    ("live-lowhold.json", M.LowHoldOpportunity),
    ("live-events.json", M.Event),
    ("live-sport.json", M.Sport),
    ("live-league.json", M.League),
    ("live-sportsbook.json", M.Sportsbook),
    ("live-teams.json", M.Team),
    ("live-markets.json", M.Market),
    ("live-account.json", M.AccountInfo),
]


def _fixture(name: str) -> dict | list:
    return json.loads((FIXTURE_DIR / name).read_text())


def _first_live_row(raw: dict | list) -> dict:
    if isinstance(raw, list):
        return raw[0]

    data = raw.get("data", raw)
    if isinstance(data, list):
        return data[0]
    return data


@pytest.mark.parametrize(("fixture_name", "model_class"), LIVE_MODEL_FIXTURES)
def test_live_api_samples_validate_against_exported_models(fixture_name, model_class):
    row = _first_live_row(_fixture(fixture_name))

    parsed = model_class.model_validate(row)

    assert parsed is not None


def test_odds_line_accepts_flat_probability_alias():
    row = _first_live_row(_fixture("live-odds.json"))

    parsed = M.OddsLine.model_validate(row)

    assert parsed.probability == row["odds_probability"]
    assert parsed.model_extra is not None


def test_live_only_opportunity_and_reference_fields_are_exposed():
    ev = M.EVOpportunity.model_validate(_first_live_row(_fixture("live-ev.json")))
    assert ev.confidence == 85.0
    assert ev.odds_probability == 0.4082
    assert (
        ev.market_id
        == "brazil_-_serie_b_botafogo_crb_2026-06-30_b3:1st_half_team_total_goals:0.5"
    )
    assert ev.sportsbooks == ["hardrock"]

    arb = M.ArbitrageOpportunity.model_validate(_first_live_row(_fixture("live-arb.json")))
    assert arb.league_label == "International - Club Friendlies"
    assert arb.market_label == "Total Goals"

    middle = M.MiddleOpportunity.model_validate(_first_live_row(_fixture("live-middles.json")))
    assert middle.side1 is not None
    assert middle.side1.odds_decimal == 3.4
    assert middle.team_name == "Boston Red Sox"
    assert middle.worst_case_pnl == -4.23

    low_hold = M.LowHoldOpportunity.model_validate(_first_live_row(_fixture("live-lowhold.json")))
    assert low_hold.side1 is not None
    assert low_hold.side1.odds_probability == 0.4854
    assert low_hold.league_label == "WTA"
    assert low_hold.market_label == "1st Set Moneyline"

    event = M.Event.model_validate(_first_live_row(_fixture("live-events.json")))
    assert event.uuid == "80868d9098da77f3"
    assert event.book_count == 3
    assert "moneyline" in event.markets

    sport = M.Sport.model_validate(_first_live_row(_fixture("live-sport.json")))
    assert sport.live_count == 203
    assert "1_deild_women" in sport.leagues

    book = M.Sportsbook.model_validate(_first_live_row(_fixture("live-sportsbook.json")))
    assert book.display_name == "SABA"
    assert book.is_sharp is False

    team = M.Team.model_validate(_first_live_row(_fixture("live-teams.json")))
    assert team.id is None
    assert team.logo == "https://cdn.opticodds.com/team-logos/soccer/6101.png"

    market = M.Market.model_validate(_first_live_row(_fixture("live-markets.json")))
    assert market.id == "outright"
    assert "football" in market.sports

    account = M.AccountInfo.model_validate(_first_live_row(_fixture("live-account.json")))
    assert account.features[:3] == ["odds", "schedule", "ev"]
    assert account.rate_limit.requests_per_minute == 10000
    assert account.streaming.enabled is True


def test_parse_response_preserves_top_level_pagination_and_updated_at():
    raw = _fixture("live-odds.json")

    response = parse_response(raw, M.OddsLine)

    assert len(response.data) == 1
    assert response.meta is not None
    assert response.meta.updated == raw["updated_at"]
    assert response.meta.pagination is not None
    assert response.meta.pagination.count == raw["pagination"]["count"]
    assert response.meta.pagination.next_cursor == raw["pagination"]["next_cursor"]
