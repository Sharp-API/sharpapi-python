"""Shared test fixtures with realistic mock API responses."""

from __future__ import annotations

API_KEY = "sk_test_abc123"
BASE_URL = "https://api.sharpapi.io"


# =============================================================================
# Mock API Responses
# =============================================================================

ARBITRAGE_RESPONSE = {
    "success": True,
    "data": [
        {
            "id": "arb_dk_pin_nba_lal_bos_ml",
            "event_id": "evt_33483153",
            "event_name": "Los Angeles Lakers @ Boston Celtics",
            "sport": "basketball",
            "league": "nba",
            "market_type": "moneyline",
            "profit_percent": 1.83,
            "implied_total": 98.2,
            "estimated_net_profit_percent": 1.63,
            "is_live": True,
            "is_alternate_line": False,
            "possibly_stale": False,
            "oldest_odds_age_seconds": 12.5,
            "warnings": ["LIVE_GAME"],
            "ev_available": True,
            "ev_percentage": 3.2,
            "is_player_prop": False,
            "legs": [
                {
                    "sportsbook": "draftkings",
                    "selection": "Los Angeles Lakers",
                    "odds_american": 145,
                    "odds_decimal": 2.45,
                    "implied_probability": 0.408,
                    "stake_percent": 41.5,
                    "timestamp": "2026-03-09T16:59:48Z",
                    "external_event_id": "dk_12345",
                    "selection_id": "sel_abc",
                },
                {
                    "sportsbook": "pinnacle",
                    "selection": "Boston Celtics",
                    "odds_american": -135,
                    "odds_decimal": 1.741,
                    "implied_probability": 0.574,
                    "stake_percent": 58.5,
                    "timestamp": "2026-03-09T16:59:50Z",
                },
            ],
            "detected_at": "2026-03-09T17:00:00Z",
        },
    ],
    "meta": {
        "count": 1,
        "pagination": {"limit": 50, "offset": 0, "has_more": False},
        "summary": {
            "count": 1,
            "avg_profit": 1.83,
            "max_profit": 1.83,
            "by_sportsbook": {"draftkings": 1, "pinnacle": 1},
        },
    },
}

EV_RESPONSE = {
    "success": True,
    "data": [
        {
            "id": "ev_dk_nba_33483153_ml_PHO",
            "game_id": "evt_123",
            "game": "PHI 76ers vs PHO Suns",
            "sport": "basketball",
            "league": "nba",
            "market": "moneyline",
            "selection": "PHO Suns",
            "sportsbook": "draftkings",
            "odds_american": -105,
            "odds_decimal": 1.952,
            "no_vig_odds": 1.912,
            "fair_probability": 0.523,
            "true_probability": 0.523,
            "ev_percentage": 4.2,
            "ev_percent": 4.2,
            "kelly_percent": 0.021,
            "kelly_fraction": 0.021,
            "confidence_score": 87,
            "book_count": 8,
            "market_width": 0.043,
            "devig_method": "power",
            "sharp_book": "pinnacle",
            "devig_book": "pinnacle",
            "is_live": False,
            "possibly_stale": False,
            "warnings": [],
            "detected_at": "2026-03-09T17:00:00Z",
        },
    ],
    "meta": {
        "count": 1,
        "summary": {"avg_ev": 4.2, "max_ev": 4.2},
    },
}

MIDDLES_RESPONSE = {
    "success": True,
    "data": [
        {
            "id": "mid_123",
            "event_id": "evt_456",
            "event_name": "Buffalo Bills @ Kansas City Chiefs",
            "sport": "football",
            "league": "nfl",
            "market_type": "point_spread",
            "home_team": "Kansas City Chiefs",
            "away_team": "Buffalo Bills",
            "side1": {
                "book": "draftkings",
                "selection": "Kansas City Chiefs",
                "line": -2.5,
                "odds": {"american": -110, "decimal": 1.909, "probability": 0.524},
            },
            "side2": {
                "book": "fanduel",
                "selection": "Buffalo Bills",
                "line": 7.5,
                "odds": {"american": -110, "decimal": 1.909, "probability": 0.524},
            },
            "middle_size": 5.0,
            "middle_numbers": [3, 4, 5, 6, 7],
            "middle_probability": 0.377,
            "expected_value": 31.52,
            "roi_percentage": 31.52,
            "quality_score": 85,
            "key_numbers": [3, 7],
            "is_live": False,
            "warnings": ["HIGH_PROBABILITY"],
            "detected_at": "2026-03-09T17:00:00Z",
        },
    ],
}

LOW_HOLD_RESPONSE = {
    "success": True,
    "data": [
        {
            "id": "lh_001",
            "event_name": "PHI 76ers vs PHO Suns",
            "sport": "basketball",
            "league": "nba",
            "market_type": "moneyline",
            "hold_percentage": 1.8,
            "is_live": False,
            "detected_at": "2026-03-09T17:00:00Z",
        },
    ],
}

ODDS_RESPONSE = {
    "success": True,
    "data": [
        {
            "id": "dk_33483153_ml_LAL",
            "sportsbook": "draftkings",
            "sportsbook_name": "DraftKings",
            "event_id": "evt_33483153",
            "sport": "basketball",
            "league": "nba",
            "home_team": "Boston Celtics",
            "away_team": "Los Angeles Lakers",
            "market_type": "moneyline",
            "selection": "Los Angeles Lakers",
            "selection_type": "away",
            "odds_american": 145,
            "odds_decimal": 2.45,
            "probability": 0.408,
            "event_start_time": "2026-03-09T23:00:00Z",
            "timestamp": "2026-03-09T17:00:00Z",
            "is_live": False,
        },
    ],
    "meta": {"count": 1},
}

SPORTS_RESPONSE = {
    "data": [
        {"id": "basketball", "name": "Basketball", "slug": "basketball", "active": True},
        {"id": "football", "name": "Football", "slug": "football", "active": True},
    ],
}

LEAGUES_RESPONSE = {
    "data": [
        {"id": "nba", "name": "NBA", "slug": "nba", "sport_id": "basketball", "active": True},
        {"id": "nfl", "name": "NFL", "slug": "nfl", "sport_id": "football", "active": True},
    ],
}

SPORTSBOOKS_RESPONSE = {
    "data": [
        {
            "id": "draftkings",
            "name": "DraftKings",
            "slug": "draftkings",
            "active": True,
            "regions": ["us"],
            "features": ["odds", "props"],
        },
    ],
}

EVENTS_RESPONSE = {
    "data": [
        {
            "id": "evt_33483153",
            "sport": "basketball",
            "league": "nba",
            "home_team": "Boston Celtics",
            "away_team": "Los Angeles Lakers",
            "start_time": "2026-03-09T23:00:00Z",
            "is_live": False,
            "status": "upcoming",
        },
    ],
}

ACCOUNT_RESPONSE = {
    "data": {
        "key": {"id": "key_abc", "tier": "pro", "userId": "usr_123"},
        "limits": {
            "requests_per_minute": 300,
            "max_streams": 5,
            "odds_delay_seconds": 0,
            "max_books": 15,
        },
        "features": {"ev": True, "arbitrage": True, "middles": True, "streaming": False},
        "add_ons": [],
    },
}

ERROR_401 = {
    "error": {"code": "invalid_api_key", "message": "Invalid API key"},
}

ERROR_403 = {
    "error": {"code": "tier_restricted", "message": "Pro tier required"},
    "required_tier": "pro",
}

ERROR_429 = {
    "error": {"code": "rate_limited", "message": "Too many requests"},
    "retry_after": 30,
}

ERROR_400 = {
    "error": {"code": "validation_error", "message": "Invalid min_ev parameter"},
}

RATE_LIMIT_HEADERS = {
    "x-ratelimit-limit": "300",
    "x-ratelimit-remaining": "297",
    "x-ratelimit-reset": "1707401000",
    "x-tier": "pro",
}
