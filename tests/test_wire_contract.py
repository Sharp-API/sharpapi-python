"""Model <-> wire contract, pinned against captured live payloads.

Issue #18 covered two model/wire mismatches:

- ``MiddleSide`` required nested ``odds: OddsValue``, but the wire sends flat
  odds fields. Every ``client.middles()`` call raised ``ValidationError``.
- ``EVOpportunity.confidence_score`` lacked an alias for ``confidence`` and
  returned ``None`` on every row, affecting consumers filtering on that field.

Captured API responses test required-field validation and silent alias failures
against the actual wire format. Refresh fixtures in ``tests/fixtures`` when the
API intentionally changes, then check whether model updates are required.

The suite does not assert that every declared field appears in these fixtures:
small samples cannot distinguish unsupported fields from conditional fields.
An earlier check flagged ``sharp_odds_american``, ``is_suspended``, and ``*_ref``
objects, which are legitimately conditional. The ``confidence_score`` alias is
therefore covered explicitly; broader coverage requires more complete fixtures.
"""

import json
import re
from pathlib import Path

import pytest

from sharpapi._base import parse_response
from sharpapi.models import (
    AccountInfo,
    BestOddsSelection,
    Event,
    EVOpportunity,
    League,
    MiddleOpportunity,
    MiddleSide,
    OddsLine,
    Sport,
    Sportsbook,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _rows(name: str) -> list[dict]:
    payload = json.loads((FIXTURES / name).read_text())
    rows = payload.get("data") or []
    assert rows, f"{name} has no rows — recapture it, an empty fixture asserts nothing"
    return rows


def _sides(rows: list[dict]) -> list[dict]:
    return [s for r in rows for k in ("side1", "side2") if (s := r.get(k))]


# --------------------------------------------------------------------------- #
# Regression guards for the two shipped defects
# --------------------------------------------------------------------------- #


def test_middles_response_parses():
    """The #18 headline: this raised ValidationError on every real payload."""
    for row in _rows("middles_live.json"):
        MiddleOpportunity.model_validate(row)


def test_middle_side_reads_flat_odds():
    for side in _sides(_rows("middles_live.json")):
        parsed = MiddleSide.model_validate(side)
        assert parsed.odds_american == side["odds_american"]
        assert parsed.odds_decimal == side["odds_decimal"]


def test_ev_confidence_score_populates_from_wire_confidence():
    """Wire sends ``confidence``; the public attribute stayed ``confidence_score``."""
    for row in _rows("ev_live.json"):
        if (wire := row.get("confidence")) is None:
            continue
        assert EVOpportunity.model_validate(row).confidence_score == pytest.approx(wire)
        break
    else:
        pytest.skip("no row carried `confidence`")


def test_ev_quality_tier_populates():
    for row in _rows("ev_live.json"):
        if (wire := row.get("quality_tier")) is None:
            continue
        assert EVOpportunity.model_validate(row).quality_tier == wire
        break
    else:
        pytest.skip("no row carried `quality_tier`")


# --------------------------------------------------------------------------- #
# The general guard — catches the next one of these, not just these two
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("model", "fixture", "extract"),
    [
        (MiddleSide, "middles_live.json", _sides),
        (EVOpportunity, "ev_live.json", lambda rows: rows),
        # Issue #23 extended fixture validation to these five models. Each
        # previously required fields absent from API responses, causing the
        # corresponding calls to raise ValidationError.
        (Sport, "sports_live.json", lambda rows: rows),
        (League, "leagues_live.json", lambda rows: rows),
        (Sportsbook, "sportsbooks_live.json", lambda rows: rows),
        (OddsLine, "odds_live.json", lambda rows: rows),
        (BestOddsSelection, "odds_best_live.json", lambda rows: rows),
    ],
    ids=[
        "MiddleSide",
        "EVOpportunity",
        "Sport",
        "League",
        "Sportsbook",
        "OddsLine",
        "BestOddsSelection",
    ],
)
def test_no_required_field_is_absent_from_the_wire(model, fixture, extract):
    """A required field the wire never sends makes the endpoint unparseable.

    This is the shape of the ``MiddleSide.odds`` bug, stated generally.
    """
    payloads = extract(_rows(fixture))
    required = {n for n, f in model.model_fields.items() if f.is_required()}
    for payload in payloads:
        missing = {
            r
            for r in required
            if r not in payload and not _satisfied_by_alias(model, r, payload)
        }
        assert not missing, (
            f"{model.__name__} requires {sorted(missing)}, absent from a live payload "
            f"— this endpoint cannot be parsed. Wire keys: {sorted(payload)}"
        )


def _satisfied_by_alias(model, field_name: str, payload: dict) -> bool:
    alias = model.model_fields[field_name].validation_alias
    if alias is None:
        return False
    choices = getattr(alias, "choices", None)
    if choices is None:
        return isinstance(alias, str) and alias in payload
    return any(isinstance(c, str) and c in payload for c in choices)


# --------------------------------------------------------------------------- #
# Version declarations are also a wire contract — with the packaging metadata
# --------------------------------------------------------------------------- #


def test_dunder_version_matches_pyproject():
    """``__version__`` and ``pyproject.toml`` are two declarations of one fact.

    Issue #13 updated ``pyproject.toml`` from 0.4.0 to 0.4.1 while leaving
    ``__init__.py`` at 0.4.0. The immutable 0.4.1 sdist therefore reports
    ``sharpapi.__version__ == "0.4.0"``. This test prevents future mismatches.

    Compare the source declarations because ``importlib.metadata`` reflects
    the last installed distribution. Stale editable-install metadata can
    differ from the current source version.
    """
    import sharpapi

    pyproject = (Path(__file__).parents[1] / "pyproject.toml").read_text()
    declared = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert declared, "no version in pyproject.toml"
    assert sharpapi.__version__ == declared.group(1)


# --------------------------------------------------------------------------- #
# Issue #23 — the reference/odds/account drift a customer hit on 0.4.1
#
# Six calls raised ValidationError against the deployed API. Each test below
# pins one cause; each fails on the pre-fix models.
# --------------------------------------------------------------------------- #


def _payload(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_reference_lists_parse():
    """sports/leagues/sportsbooks .list() — all three raised on every call."""
    for fixture, model in (
        ("sports_live.json", Sport),
        ("leagues_live.json", League),
        ("sportsbooks_live.json", Sportsbook),
    ):
        for row in _rows(fixture):
            model.model_validate(row)


def test_league_name_reads_wire_display_name():
    for row in _rows("leagues_live.json"):
        assert "name" not in row, "wire started sending `name` — revisit the alias"
        assert League.model_validate(row).name == row["display_name"]


def test_sportsbook_name_reads_wire_display_name():
    for row in _rows("sportsbooks_live.json"):
        assert "name" not in row, "wire started sending `name` — revisit the alias"
        assert Sportsbook.model_validate(row).name == row["display_name"]


def test_sportsbook_active_derives_from_status_string():
    """The wire carries availability as ``status: "active"``, not a boolean."""
    for row in _rows("sportsbooks_live.json"):
        assert isinstance(row["status"], str)
        assert Sportsbook.model_validate(row).active is (row["status"] == "active")
    # The branch no live fixture covers: a book that is not active.
    dark = Sportsbook.model_validate({"id": "x", "display_name": "X", "status": "outage"})
    assert dark.active is False
    # An explicit boolean in the payload still wins over the derivation.
    both = Sportsbook.model_validate(
        {"id": "x", "display_name": "X", "status": "outage", "active": True}
    )
    assert both.active is True


def test_odds_probability_populates_from_wire_odds_probability():
    """The wire kept the ``odds_`` prefix on this field and the model did not."""
    for row in _rows("odds_live.json"):
        assert "probability" not in row
        assert OddsLine.model_validate(row).probability == pytest.approx(
            row["odds_probability"]
        )


def test_account_features_is_a_list_of_names():
    """Declared as an object of booleans; the wire sends a flat list."""
    data = _payload("account_live.json")["data"]
    assert isinstance(data["features"], list)
    acct = AccountInfo.model_validate(data)
    assert acct.features == data["features"]
    assert acct.has_feature(data["features"][0])
    assert not acct.has_feature("definitely-not-a-feature")


def test_best_odds_is_not_an_odds_line():
    """/odds/best returns a different row shape; it was typed list[OddsLine]."""
    rows = _rows("odds_best_live.json")
    for row in rows:
        assert "odds_american" not in row, "shape changed — /odds/best now flat?"
        BestOddsSelection.model_validate(row)
    parsed = BestOddsSelection.model_validate(rows[0])
    assert parsed.best_book and parsed.all_books
    assert parsed.best_odds is not None


def test_null_data_parses_as_empty_list():
    """List endpoints send ``"data": null`` — not ``[]`` — when nothing matches.

    ``raw.get("data", [])`` does not defend against this: the default only
    fires when the key is absent, and here it is present and null. This test
    covers filters with no matching events.
    """
    payload = _payload("events_empty_live.json")
    assert payload["data"] is None, "recapture: this fixture must carry a null data"
    assert parse_response(payload, Event).data == []
