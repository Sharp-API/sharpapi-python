"""Pydantic models for SharpAPI responses."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

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
    next_offset: int | None = None
    total: int | None = None


class ResponseMeta(BaseModel):
    """Metadata returned with API responses."""

    count: int | None = None
    total: int | None = None
    pagination: Pagination | None = None
    updated: str | None = None
    source: str | None = None
    last_update: str | None = None
    data_age_seconds: float | None = None
    filters: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    books_analyzed: int | None = None


class APIResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""

    success: bool | None = None
    data: T
    meta: ResponseMeta | None = None
    timestamp: str | None = None
    tier: str | None = None

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
            if isinstance(item, BaseModel):
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

    period: str | None = None
    clock: str | None = None
    score_home: int | None = None
    score_away: int | None = None


# =============================================================================
# Odds
# =============================================================================


class OddsLine(BaseModel):
    """A single odds line from a sportsbook."""

    id: str
    sportsbook: str
    sportsbook_name: str | None = None
    event_id: str
    sport: str
    league: str
    home_team: str
    away_team: str
    market_type: str
    selection: str
    selection_type: str | None = None
    odds_american: int | float
    odds_decimal: float
    probability: float
    line: float | None = None
    event_start_time: str | None = None
    timestamp: str | None = None
    is_live: bool = False
    deep_link: str | None = None
    player_name: str | None = None
    stat_category: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    game_period: str | None = None
    game_clock: str | None = None


# =============================================================================
# EV Opportunities
# =============================================================================


class EVOpportunity(BaseModel):
    """A positive expected value (+EV) opportunity."""

    id: str
    event_id: str | None = Field(None, alias="game_id")
    event_name: str | None = Field(None, alias="game")
    sport: str
    league: str
    market_type: str | None = Field(None, alias="market")
    selection: str
    sportsbook: str
    odds_american: int | float
    odds_decimal: float
    no_vig_odds: float | None = None
    fair_probability: float | None = Field(
        None, validation_alias=AliasChoices("fair_probability", "true_probability")
    )
    ev_percentage: float = Field(
        validation_alias=AliasChoices("ev_percentage", "ev_percent")
    )
    kelly_percent: float | None = Field(
        None, validation_alias=AliasChoices("kelly_percent", "kelly_fraction")
    )
    confidence_score: float | None = None
    book_count: int | None = None
    market_width: float | None = None
    devig_method: str | None = None
    sharp_book: str | None = Field(
        None, validation_alias=AliasChoices("sharp_book", "devig_book")
    )
    sharp_odds_american: int | float | None = None
    sharp_odds_decimal: float | None = None
    line: float | None = None
    home_team: str | None = None
    away_team: str | None = None
    start_time: str | None = None
    is_live: bool = False
    arb_available: bool | None = None
    arb_profit: float | None = None
    is_player_prop: bool = False
    player_name: str | None = None
    stat_category: str | None = None
    possibly_stale: bool = False
    oldest_odds_age_seconds: float | None = None
    warnings: list[str] = Field(default_factory=list)
    detected_at: str | None = None
    external_event_id: str | None = None
    selection_id: str | None = None

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
    implied_probability: float | None = None
    stake_percent: float
    timestamp: str | None = None
    external_event_id: str | None = None
    selection_id: str | None = None
    market_id: str | None = None


class ArbitrageOpportunity(BaseModel):
    """A guaranteed-profit arbitrage opportunity."""

    id: str
    event_id: str | None = None
    event_name: str
    sport: str
    league: str | None = None
    market_type: str
    line: float | None = None
    profit_percent: float
    implied_total: float | None = None
    estimated_net_profit_percent: float | None = None
    start_time: str | None = None
    is_live: bool = False
    is_alternate_line: bool = False
    possibly_stale: bool = False
    oldest_odds_age_seconds: float | None = None
    warnings: list[str] = Field(default_factory=list)
    game_state: GameState | None = None
    ev_available: bool | None = None
    ev_percentage: float | None = None
    is_player_prop: bool = False
    player_name: str | None = None
    stat_category: str | None = None
    legs: list[ArbitrageLeg]
    detected_at: str | None = None


# =============================================================================
# Middle Opportunities
# =============================================================================


class MiddleSide(BaseModel):
    """One side of a middle opportunity."""

    book: str
    selection: str
    line: float
    odds: OddsValue
    stake_percent: float | None = None
    odds_age_seconds: float | None = None
    deep_link: str | None = None


class MiddleOpportunity(BaseModel):
    """A middle opportunity where both sides can win."""

    id: str
    event_id: str | None = None
    event_name: str
    sport: str
    league: str | None = None
    market_type: str
    home_team: str | None = None
    away_team: str | None = None
    start_time: str | None = None
    side1: MiddleSide | None = None
    side2: MiddleSide | None = None
    middle_size: float | None = None
    middle_numbers: list[int] | None = None
    middle_probability: float | None = None
    expected_value: float | None = None
    roi_percentage: float | None = None
    worst_case_loss: float | None = None
    best_case_profit: float | None = None
    break_even_percent: float | None = None
    is_guaranteed_profit: bool = False
    guaranteed_roi: float | None = None
    key_numbers: list[int] | None = None
    key_number_probability: float | None = None
    quality_score: float | None = None
    market_overround: float | None = None
    is_live: bool = False
    game_state: GameState | None = None
    is_player_prop: bool = False
    player_name: str | None = None
    stat_category: str | None = None
    odds_age_seconds: float | None = None
    warnings: list[str] = Field(default_factory=list)
    detected_at: str | None = None
    # Flat fields (alternative to side1/side2 nesting)
    gap_size: float | None = Field(None, alias="gapSize")
    potential_profit: float | None = Field(None, alias="potentialProfit")
    legs: list[ArbitrageLeg] | None = None

    model_config = {"populate_by_name": True}


# =============================================================================
# Low Hold
# =============================================================================


class LowHoldSide(BaseModel):
    """One side of a low-hold opportunity."""

    selection: str
    books: list[str] | None = None
    line: float | None = None
    odds: OddsValue | None = None
    deep_links: dict[str, str] | None = None


class LowHoldOpportunity(BaseModel):
    """A low-hold (low vig) market."""

    id: str
    event_id: str | None = None
    event_name: str
    sport: str
    league: str | None = None
    market_type: str
    line: float | None = None
    home_team: str | None = None
    away_team: str | None = None
    start_time: str | None = None
    hold_percentage: float
    side1: LowHoldSide | None = None
    side2: LowHoldSide | None = None
    side3: LowHoldSide | None = None
    is_live: bool = False
    game_state: GameState | None = None
    is_alternate_line: bool = False
    all_books: list[str] | None = None
    confidence: float | None = None
    odds_age_seconds: float | None = None
    possibly_stale: bool = False
    is_player_prop: bool = False
    player_name: str | None = None
    stat_category: str | None = None
    detected_at: str | None = None


# =============================================================================
# Reference Data
# =============================================================================


class Sport(BaseModel):
    id: str
    name: str
    slug: str
    active: bool
    event_count: int | None = None


class League(BaseModel):
    id: str
    name: str
    slug: str
    sport_id: str | None = None
    country: str | None = None
    active: bool


class Sportsbook(BaseModel):
    id: str
    name: str
    slug: str
    active: bool
    regions: list[str] | None = None
    features: list[str] | None = None


class Event(BaseModel):
    id: str
    sport: str
    league: str
    home_team: str
    away_team: str
    start_time: str | None = None
    is_live: bool = False
    status: str | None = None


class Market(BaseModel):
    """A market available on an event."""

    market_type: str
    market_label: str | None = None
    selection_count: int | None = None
    book_count: int | None = None
    books: list[str] | None = None


# =============================================================================
# Closing Snapshot
# =============================================================================


class ClosingOddsLine(BaseModel):
    """A single closing-line odds entry within a closing snapshot."""

    sportsbook: str
    market_type: str
    selection: str
    selection_type: str | None = None
    odds_american: int | float
    odds_decimal: float
    line: float | None = None
    player_name: str | None = None
    stat_category: str | None = None


class ClosingSnapshot(BaseModel):
    """Closing-line snapshot for an event, grouped by sportsbook."""

    event_id: str
    sport: str | None = None
    league: str | None = None
    home_team: str | None = None
    away_team: str | None = None
    event_start_time: str | None = None
    captured_at: str | None = None
    books: dict[str, list[ClosingOddsLine]] = Field(default_factory=dict)


# =============================================================================
# Account / Keys
# =============================================================================


class APIKey(BaseModel):
    """An API key managed via the /account/keys endpoints."""

    id: str
    id_masked: str | None = None
    # Present only on create/rotate responses (one-time secret).
    key: str | None = None
    name: str | None = None
    tier: str | None = None
    is_active: bool | None = None
    created_at: str | None = None
    updated_at: str | None = None


# =============================================================================
# Account
# =============================================================================


class AccountLimits(BaseModel):
    requests_per_minute: int | None = None
    max_streams: int | None = None
    odds_delay_seconds: int | None = None
    max_books: int | None = None


class AccountFeatures(BaseModel):
    ev: bool = False
    arbitrage: bool = False
    middles: bool = False
    streaming: bool = False


class AccountInfo(BaseModel):
    key: dict[str, Any] | None = None
    limits: AccountLimits | None = None
    features: AccountFeatures | None = None
    add_ons: list[str] | None = None


class RateLimitInfo(BaseModel):
    """Rate limit state from response headers."""

    limit: int | None = None
    remaining: int | None = None
    reset: float | None = None
    tier: str | None = None
