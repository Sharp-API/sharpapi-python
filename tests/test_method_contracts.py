import httpx

from sharpapi import SharpAPI
from sharpapi.streaming import _parse_sse


def test_odds_comparison_uses_event_query_param(monkeypatch):
    client = SharpAPI("sk_test")
    captured = {}

    def fake_get(path, params=None):
        captured["path"] = path
        captured["params"] = params
        return {"data": []}

    monkeypatch.setattr(client, "_get", fake_get)

    client.odds.comparison("evt_123", market="moneyline")

    assert captured["path"] == "/odds/comparison"
    assert captured["params"]["event"] == "evt_123"
    assert "event_id" not in captured["params"]
    client.close()


def test_odds_batch_parses_events_object_shape(monkeypatch):
    client = SharpAPI("sk_test")
    odds_row = {
        "id": "odd_1",
        "sportsbook": "pinnacle",
        "event_id": "evt_1",
        "sport": "tennis",
        "league": "wta",
        "home_team": "A",
        "away_team": "B",
        "market_type": "moneyline",
        "selection": "A",
        "selection_type": "home",
        "odds_american": -110,
        "odds_decimal": 1.91,
        "odds_probability": 0.5238,
        "is_live": False,
        "timestamp": "2026-06-30T00:00:00Z",
    }

    monkeypatch.setattr(
        client,
        "_post",
        lambda path, json_body=None: {
            "data": {"events": {"evt_1": [odds_row]}, "missing_events": ["evt_2"]},
            "updated_at": "2026-06-30T00:00:00Z",
        },
    )

    response = client.odds.batch(["evt_1", "evt_2"])

    assert response.data.events["evt_1"][0].event_id == "evt_1"
    assert response.data.missing_events == ["evt_2"]
    assert response.updated_at == "2026-06-30T00:00:00Z"
    client.close()


def test_arbitrage_csv_returns_raw_text_from_configured_client(monkeypatch):
    client = SharpAPI("sk_test", base_url="https://staging.example")
    captured = {}

    def fake_request(method, path, params=None, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["params"] = params
        request = httpx.Request(method, f"https://staging.example/api/v1{path}")
        return httpx.Response(200, text="event_id,profit_percent\n", request=request)

    monkeypatch.setattr(client._http, "request", fake_request)

    csv = client.arbitrage.csv(sport="soccer", limit=10)

    assert csv == "event_id,profit_percent\n"
    assert captured == {
        "method": "GET",
        "path": "/opportunities/arbitrage",
        "params": {"sport": "soccer", "limit": 10, "format": "csv"},
    }
    client.close()


def test_stream_event_and_gamestate_use_unified_stream_contract():
    client = SharpAPI("sk_test", base_url="https://staging.example")

    event_url = httpx.URL(client.stream.event("evt_123")._url)
    assert event_url.path == "/api/v1/stream"
    assert event_url.params["channel"] == "odds"
    assert event_url.params["event"] == "evt_123"

    gamestate_url = httpx.URL(client.stream.gamestate()._url)
    assert gamestate_url.path == "/api/v1/stream"
    assert gamestate_url.params["channel"] == "gamestate"
    client.close()


def test_parse_sse_surfaces_event_ids_for_reconnect_resume():
    events = list(
        _parse_sse(
            iter(
                [
                    "id: evt-1",
                    "event: odds:update",
                    'data: {"ok": true}',
                    "",
                ]
            )
        )
    )

    assert events == [("__id__", "evt-1"), ("odds:update", {"ok": True})]
