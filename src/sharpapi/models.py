"""Pydantic models for SharpAPI responses."""

from __future__ import annotations

from typing import Any, Generic, List, Optional, TypeVar

from pydantic import AliasChoices, BaseModel, Field

T = TypeVar("T")


# =============================================================================
# Common
# =============================================================================


class OddsValue(BaseModel):
    """Odds in multiple formats."""

    american: int | float
    decimal: float
    probability: float


class Pagination(BaseModel):
    limit: int
    offset: int
    has_more: bool
    next_offset: Optional[int] = None
    total: Optional[int] = None


class ResponseMeta(BaseModel):
    """Metadata returned with API responses."""

    count: Optional[int] = None
    total: Optional[int] = None
    pagination: Optional[Pagination] = None
    updated: Optional[str] = None
    source: Optional[str] = None
    last_update: Optional[str] = None
    data_age_seconds: Optional[float] = None
    filters: Optional[dict[str, Any]] = None
    summary: Optional[dict[str, Any]] = None
    books_analyzed: Optional[int] = None


class APIResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""

    success: Optional[bool] = None
    data: T
    meta: Optional[ResponseMeta] = None
    timestamp: Optional[str] = None
    tier: Optional[str] = None

    def to_dataframe(self, flatten: bool = True):
        """Convert response data to a pandas DataFrame.

        Requires ``pip install sharpapi[pandas]``.

        Args:
            flatten: If True (default), flatten nested objects like
                ``game_state.period`` into ``game_state_period`` columns.
                Nested lists (like ``legs``) remain as-is.

        Returns:
            pandas.DataFrame with one row per item in ``data``.
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "pandas is required for to_dataframe(). "
                "Install it with: pip install sharpapi[pandas]"
            ) from None

        data = self.data
        if not data:
            return pd.DataFrame()

        if not isinstance(data, list):
            data = [data]

        rows = []
        for item in data:
            if hasattr(item, "model_dump"):
                row = item.model_dump()
            else:
                row = dict(item) if isinstance(item, dict) else {"value": item}

            if flatten:
                row = _flatten_dict(row)
            rows.append(row)

        return pd.DataFrame(rows)


def _flatten_dict(d: dict, parent_key: str = "", sep: str = "_") -> dict:
    """Flatten nested dicts, skip lists."""
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


class GameState(BaseModel):
    """Live game state."""

    period: Optional[str] = None
    clock: Optional[str] = None
    score_home: Optional[int] = None
    score_away: Optional[int] = None


# =============================================================================
# Odds
# =============================================================================


class OddsLine(BaseModel):
    """A single odds line from a sportsbook."""

    id: str
    sportsbook: str
    sportsbook_name: Optional[str] = None
    event_id: str
    sport: str
    league: str
    home_team: str
    away_team: str
    market_type: str
    selection: str
    selection_type: Optional[str] = None
    odds_american: int | float
    odds_decimal: float
    probability: float
    line: Optional[float] = None
    event_start_time: Optional[str] = None
    timestamp: Optional[str] = None
    is_live: bool = False
    deep_link: Optional[str] = None
    player_name: Optional[str] = None
    stat_category: Optional[str] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    game_period: Optional[str] = None
    game_clock: Optional[str] = None


# =============================================================================
# EV Opportunities
# =============================================================================


class EVOpportunity(BaseModel):
    """A positive expected value (+EV) opportunity."""

    id: str
    event_id: Optional[str] = Field(None, alias="game_id")
    event_name: Optional[str] = Field(None, alias="game")
    sport: str
    league: str
    market_type: Optional[str] = Field(None, alias="market")
    selection: str
    sportsbook: str
    odds_american: int | float
    odds_decimal: float
    no_vig_odds: Optional[float] = None
    fair_probability: Optional[float] = Field(
        None, validation_alias=AliasChoices("fair_probability", "true_probability")
    )
    ev_percentage: float = Field(
        validation_alias=AliasChoices("ev_percentage", "ev_percent")
    )
    kelly_percent: Optional[float] = Field(
        None, validation_alias=AliasChoices("kelly_percent", "kelly_fraction")
    )
    confidence_score: Optional[float] = None
    book_count: Optional[int] = None
    market_width: Optional[float] = None
    devig_method: Optional[str] = None
    sharp_book: Optional[str] = Field(
        None, validation_alias=AliasChoices("sharp_book", "devig_book")
    )
    sharp_odds_american: Optional[int | float] = None
    sharp_odds_decimal: Optional[float] = None
    line: Optional[float] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    start_time: Optional[str] = None
    is_live: bool = False
    arb_available: Optional[bool] = None
    arb_profit: Optional[float] = None
    is_player_prop: bool = False
    player_name: Optional[str] = None
    stat_category: Optional[str] = None
    possibly_stale: bool = False
    oldest_odds_age_seconds: Optional[float] = None
    warnings: List[str] = Field(default_factory=list)
    detected_at: Optional[str] = None
    external_event_id: Optional[str] = None
    selection_id: Optional[str] = None

    model_config = {"populate_by_name": True}


# =============================================================================
# Arbitrage Opportunities
# =============================================================================


class ArbitrageLeg(BaseModel):
    """One leg of an arbitrage opportunity."""

    sportsbook: str
    selection: str
    odds_american: int | float
    odds_decimal: float
    implied_probability: Optional[float] = None
    stake_percent: float
    timestamp: Optional[str] = None
    external_event_id: Optional[str] = None
    selection_id: Optional[str] = None
    market_id: Optional[str] = None


class ArbitrageOpportunity(BaseModel):
    """A guaranteed-profit arbitrage opportunity."""

    id: str
    event_id: Optional[str] = None
    event_name: str
    sport: str
    league: Optional[str] = None
    market_type: str
    line: Optional[float] = None
    profit_percent: float
    implied_total: Optional[float] = None
    estimated_net_profit_percent: Optional[float] = None
    start_time: Optional[str] = None
    is_live: bool = False
    is_alternate_line: bool = False
    possibly_stale: bool = False
    oldest_odds_age_seconds: Optional[float] = None
    warnings: List[str] = Field(default_factory=list)
    game_state: Optional[GameState] = None
    ev_available: Optional[bool] = None
    ev_percentage: Optional[float] = None
    is_player_prop: bool = False
    player_name: Optional[str] = None
    stat_category: Optional[str] = None
    legs: List[ArbitrageLeg]
    detected_at: Optional[str] = None


# =============================================================================
# Middle Opportunities
# =============================================================================


class MiddleSide(BaseModel):
    """One side of a middle opportunity."""

    book: str
    selection: str
    line: float
    odds: OddsValue
    stake_percent: Optional[float] = None
    odds_age_seconds: Optional[float] = None
    deep_link: Optional[str] = None


class MiddleOpportunity(BaseModel):
    """A middle opportunity where both sides can win."""

    id: str
    event_id: Optional[str] = None
    event_name: str
    sport: str
    league: Optional[str] = None
    market_type: str
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    start_time: Optional[str] = None
    side1: Optional[MiddleSide] = None
    side2: Optional[MiddleSide] = None
    middle_size: Optional[float] = None
    middle_numbers: Optional[List[int]] = None
    middle_probability: Optional[float] = None
    expected_value: Optional[float] = None
    roi_percentage: Optional[float] = None
    worst_case_loss: Optional[float] = None
    best_case_profit: Optional[float] = None
    break_even_percent: Optional[float] = None
    is_guaranteed_profit: bool = False
    guaranteed_roi: Optional[float] = None
    key_numbers: Optional[List[int]] = None
    key_number_probability: Optional[float] = None
    quality_score: Optional[float] = None
    market_overround: Optional[float] = None
    is_live: bool = False
    game_state: Optional[GameState] = None
    is_player_prop: bool = False
    player_name: Optional[str] = None
    stat_category: Optional[str] = None
    odds_age_seconds: Optional[float] = None
    warnings: List[str] = Field(default_factory=list)
    detected_at: Optional[str] = None
    # Flat fields (alternative to side1/side2 nesting)
    gap_size: Optional[float] = Field(None, alias="gapSize")
    potential_profit: Optional[float] = Field(None, alias="potentialProfit")
    legs: Optional[List[ArbitrageLeg]] = None

    model_config = {"populate_by_name": True}


# =============================================================================
# Low Hold
# =============================================================================


class LowHoldSide(BaseModel):
    """One side of a low-hold opportunity."""

    selection: str
    books: Optional[List[str]] = None
    line: Optional[float] = None
    odds: Optional[OddsValue] = None
    deep_links: Optional[dict[str, str]] = None


class LowHoldOpportunity(BaseModel):
    """A low-hold (low vig) market."""

    id: str
    event_id: Optional[str] = None
    event_name: str
    sport: str
    league: Optional[str] = None
    market_type: str
    line: Optional[float] = None
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    start_time: Optional[str] = None
    hold_percentage: float
    side1: Optional[LowHoldSide] = None
    side2: Optional[LowHoldSide] = None
    side3: Optional[LowHoldSide] = None
    is_live: bool = False
    game_state: Optional[GameState] = None
    is_alternate_line: bool = False
    all_books: Optional[List[str]] = None
    confidence: Optional[float] = None
    odds_age_seconds: Optional[float] = None
    possibly_stale: bool = False
    is_player_prop: bool = False
    player_name: Optional[str] = None
    stat_category: Optional[str] = None
    detected_at: Optional[str] = None


# =============================================================================
# Reference Data
# =============================================================================


class Sport(BaseModel):
    id: str
    name: str
    slug: str
    active: bool
    event_count: Optional[int] = None


class League(BaseModel):
    id: str
    name: str
    slug: str
    sport_id: Optional[str] = None
    country: Optional[str] = None
    active: bool


class Sportsbook(BaseModel):
    id: str
    name: str
    slug: str
    active: bool
    regions: Optional[List[str]] = None
    features: Optional[List[str]] = None


class Event(BaseModel):
    id: str
    sport: str
    league: str
    home_team: str
    away_team: str
    start_time: Optional[str] = None
    is_live: bool = False
    status: Optional[str] = None


# =============================================================================
# Account
# =============================================================================


class AccountLimits(BaseModel):
    requests_per_minute: Optional[int] = None
    max_streams: Optional[int] = None
    odds_delay_seconds: Optional[int] = None
    max_books: Optional[int] = None


class AccountFeatures(BaseModel):
    ev: bool = False
    arbitrage: bool = False
    middles: bool = False
    streaming: bool = False


class AccountInfo(BaseModel):
    key: Optional[dict[str, Any]] = None
    limits: Optional[AccountLimits] = None
    features: Optional[AccountFeatures] = None
    add_ons: Optional[List[str]] = None


class RateLimitInfo(BaseModel):
    """Rate limit state from response headers."""

    limit: Optional[int] = None
    remaining: Optional[int] = None
    reset: Optional[float] = None
    tier: Optional[str] = None
