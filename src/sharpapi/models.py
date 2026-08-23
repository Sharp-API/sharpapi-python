"""Pydantic models for SharpAPI responses."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import AliasChoices, BaseModel, Field, model_validator

T = TypeVar("T")


# =============================================================================
# Common
# =============================================================================


class OddsValue(BaseModel):
    """Odds in multiple formats."""

    american: int | float
    decimal: float
    probability: float


# =============================================================================
# Nested reference objects
# =============================================================================
#
# These structured ref objects ship alongside the legacy flat fields on every
# odds row, opportunity row, and reference-list row. All fields are optional
# and additive — clients on older API versions simply receive ``None``.
#
# Wire format uses snake_case (``sport_ref``, ``league_ref``, ``market_ref``,
# ``sportsbook_ref``) which Python attribute names match directly.


class TeamRef(BaseModel):
    """Structured team reference attached to ``home`` / ``away``.

    ``abbreviation`` is only present for ~1500 team-sport entities; absent
    for individual-sport competitors (tennis players, MMA fighters, etc).

    Optional metadata fields (``logo``, ``city``, ``mascot``, ``conference``,
    ``division``) are populated for the majority of major-league teams
    (~93% coverage on ``logo``, similar on the rest). Unmapped rows simply
    leave the field absent rather than emitting null.
    """

    id: str | None = None
    numerical_id: int | None = None
    name: str | None = None
    abbreviation: str | None = None
    logo: str | None = None
    city: str | None = None
    mascot: str | None = None
    conference: str | None = None
    division: str | None = None

    model_config = {"extra": "allow"}


class SportRef(BaseModel):
    """Structured sport reference attached to ``sport_ref``."""

    id: str | None = None
    name: str | None = None
    numerical_id: int | None = None

    model_config = {"extra": "allow"}


class EntityRef(BaseModel):
    """Structured reference for league / market / sportsbook objects.

    Used by ``league_ref``, ``market_ref``, and ``sportsbook_ref`` on
    every odds, opportunity, and reference row.
    """

    id: str | None = None
    label: str | None = None
    numerical_id: int | None = None

    model_config = {"extra": "allow"}


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
    # Top-level freshness stamp sent by the list endpoints.
    updated_at: str | None = None
    tier: str | None = None

    def to_dataframe(self, flatten: bool = True):
        """Convert response data to a pandas DataFrame.

        Requires ``pip install sharpapi[pandas]``.

        Args:
            flatten: If True (default), flatten nested objects into
                underscore-joined columns. Nested lists (like ``legs``)
                remain as-is.

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
    """Live game state for a single event, merged across sportsbooks.

    Returned by ``/api/v1/gamestate`` and the ``gamestate`` stream channel.
    Scores are consensus-merged with period-guarded outlier rejection;
    period/clock are picked from the most-advanced book. Not present on
    EV / arb / low-hold opportunity rows — correlate by ``event_id``.

    ``extra="allow"`` lets adapter-specific fields pass through unchanged.
    """

    home_score: int | None = None
    away_score: int | None = None
    game_period: str | None = None
    game_clock: str | None = None
    home_team: str | None = None
    away_team: str | None = None
    sport: str | None = None
    primary_book: str | None = None
    book_count: int | None = None
    stale: bool = False
    aggregator_stale: bool = False

    model_config = {"extra": "allow"}


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
    # Structured side/segment axes (issue #76 / #689). team_side is the raw
    # "home"|"away"|"draw" decomposed out of the compound selection_type vocab;
    # market_segment is the contest slice ("full_game", "1st_half", ...). Both
    # optional + additive — absent on rows the adapter didn't stamp.
    team_side: str | None = None
    market_segment: str | None = None
    odds_american: int | float
    odds_decimal: float
    # The wire names this third sibling ``odds_probability`` — the ``odds_``
    # prefix it kept on the other two. ``probability`` stays the public
    # attribute; the alias is what makes /odds parseable at all (issue #23).
    probability: float = Field(
        validation_alias=AliasChoices("odds_probability", "probability")
    )
    line: float | None = None
    event_start_time: str | None = None
    # ISO 8601 — when SharpAPI last refreshed this odd through its pipeline
    # (advances every ingest cycle). A feed-freshness / delivery signal matching
    # OpticOdds' `timestamp`; NOT a price-last-changed time. (SHA-1048)
    timestamp: str | None = None
    is_live: bool = False
    # True (default) = market open and bettable; False = market suspended/closed
    # with the price frozen (mirrors OpticOdds locked-odds). Absent on the wire
    # is treated as True. SHA-3803.
    is_active: bool = True
    deep_link: str | None = None
    player_name: str | None = None
    stat_category: str | None = None
    # Optional structured refs (additive, non-breaking).
    home: TeamRef | None = None
    away: TeamRef | None = None
    sport_ref: SportRef | None = None
    league_ref: EntityRef | None = None
    market_ref: EntityRef | None = None
    sportsbook_ref: EntityRef | None = None


# =============================================================================
# Best Odds  (GET /odds/best)
# =============================================================================
#
# /odds/best does NOT return OddsLine rows. It returns one row per selection
# with the best price, the consensus price, and every book's quote — a
# different shape entirely. It was typed as ``list[OddsLine]``, so the call
# raised ValidationError on every response (issue #23).


class BestOddsQuote(BaseModel):
    """A price block as it appears inside a /odds/best row."""

    american: int | float | None = None
    decimal: float | None = None
    probability: float | None = Field(
        None, validation_alias=AliasChoices("odds_probability", "probability")
    )

    model_config = {"populate_by_name": True, "extra": "allow"}


class BestOddsBook(BaseModel):
    """One book's quote within ``BestOddsSelection.all_books``."""

    book: str | None = None
    sportsbook: str | None = None
    odds: BestOddsQuote | None = None
    edge: float | None = None

    model_config = {"extra": "allow"}


class BestOddsSelection(BaseModel):
    """One selection's best price across all books."""

    event_id: str
    event_name: str | None = None
    sport: str | None = None
    league: str | None = None
    market_type: str | None = None
    selection: str | None = None
    line: float | None = None
    is_main_line: bool | None = None
    best_odds: BestOddsQuote | None = None
    consensus_odds: BestOddsQuote | None = None
    market_hold: float | None = None
    best_book: str | None = None
    all_books: list[BestOddsBook] = Field(default_factory=list)
    timestamp: str | None = None

    model_config = {"extra": "allow"}


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
    # The wire field is `confidence` (int 0-100). Aliased rather than renamed so
    # the public attribute name is unchanged — before this, `confidence_score`
    # silently read None on every row (#18).
    confidence_score: float | None = Field(
        None, validation_alias=AliasChoices("confidence", "confidence_score")
    )
    quality_tier: str | None = None
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
    # Structured side/segment axes (issue #76 / #689), additive + optional.
    team_side: str | None = None
    market_segment: str | None = None
    # Suspended-state (server flag EV_SUSPENDED_STATE), additive + optional. While the sharp
    # reference is momentarily suspended the opp stays visible with is_suspended=True and the
    # edge hidden (ev_percentage is 0 / unknown — never a stale edge); suspended_since is the
    # unix-seconds timestamp the suspension began. Absent unless the server flag is enabled.
    is_suspended: bool = False
    suspended_since: float | None = None
    # Optional structured refs (additive, non-breaking).
    home: TeamRef | None = None
    away: TeamRef | None = None
    sport_ref: SportRef | None = None
    league_ref: EntityRef | None = None
    market_ref: EntityRef | None = None
    sportsbook_ref: EntityRef | None = None

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
    # ISO 8601 last-refreshed (feed-freshness) timestamp for this leg's odd —
    # see OddsLine.timestamp. (SHA-1048)
    timestamp: str | None = None
    external_event_id: str | None = None
    selection_id: str | None = None
    market_id: str | None = None
    # Optional structured book ref on each leg.
    sportsbook_ref: EntityRef | None = None


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
    ev_available: bool | None = None
    ev_percentage: float | None = None
    is_player_prop: bool = False
    player_name: str | None = None
    stat_category: str | None = None
    legs: list[ArbitrageLeg]
    detected_at: str | None = None
    # Optional structured refs (additive, non-breaking).
    home: TeamRef | None = None
    away: TeamRef | None = None
    sport_ref: SportRef | None = None
    league_ref: EntityRef | None = None
    market_ref: EntityRef | None = None


# =============================================================================
# Middle Opportunities
# =============================================================================


class MiddleSide(BaseModel):
    """One side of a middle opportunity.

    Odds are **flat** on the wire — ``odds_american`` / ``odds_decimal`` /
    ``odds_probability`` — the same shape ``EVOpportunity`` uses, not a nested
    ``OddsValue``. This previously declared a required ``odds: OddsValue``, which
    is absent from every real payload, so ``client.middles()`` raised
    ``ValidationError`` on any response carrying a side (#18).
    """

    book: str
    selection: str
    line: float
    odds_american: int | float
    odds_decimal: float
    odds_probability: float | None = None
    fair_probability: float | None = None
    stake_percent: float | None = None
    odds_age_seconds: float | None = None
    external_event_id: str | None = None
    market_id: str | None = None
    selection_id: str | None = None
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
    # Optional structured refs (additive, non-breaking).
    home: TeamRef | None = None
    away: TeamRef | None = None
    sport_ref: SportRef | None = None
    league_ref: EntityRef | None = None
    market_ref: EntityRef | None = None

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
    is_alternate_line: bool = False
    all_books: list[str] | None = None
    confidence: float | None = None
    odds_age_seconds: float | None = None
    possibly_stale: bool = False
    is_player_prop: bool = False
    player_name: str | None = None
    stat_category: str | None = None
    detected_at: str | None = None
    # Optional structured refs (additive, non-breaking).
    home: TeamRef | None = None
    away: TeamRef | None = None
    sport_ref: SportRef | None = None
    league_ref: EntityRef | None = None
    market_ref: EntityRef | None = None


# =============================================================================
# Reference Data
# =============================================================================


class Sport(BaseModel):
    id: str
    name: str
    # ``slug`` and ``active`` have never appeared on /sports. They were
    # declared required and made every ``sports.list()`` call raise
    # ValidationError (issue #23). Optional, so existing readers still
    # type-check — they now read ``None`` instead of crashing.
    slug: str | None = None
    active: bool | None = None
    event_count: int | None = None
    live_count: int | None = None
    # League ids belonging to this sport — the wire sends bare id strings.
    leagues: list[str] | None = None
    # Optional integer numerical ID, additive.
    numerical_id: int | None = None

    model_config = {"extra": "allow"}


class League(BaseModel):
    id: str
    # The wire calls this ``display_name``. Aliased rather than renamed so
    # ``league.name`` keeps working for anyone already reading it.
    name: str = Field(validation_alias=AliasChoices("display_name", "name"))
    # Never sent by /leagues — see the note on ``Sport`` (issue #23).
    slug: str | None = None
    active: bool | None = None
    # The wire sends the sport as ``sport``; ``sport_id`` is the legacy name.
    sport: str | None = None
    sport_id: str | None = None
    country: str | None = None
    event_count: int | None = None
    live_count: int | None = None
    # Optional integer numerical ID, additive.
    numerical_id: int | None = None

    model_config = {"populate_by_name": True, "extra": "allow"}


class Sportsbook(BaseModel):
    id: str
    # As on ``League``: the wire calls this ``display_name``.
    name: str = Field(validation_alias=AliasChoices("display_name", "name"))
    short_name: str | None = None
    # Never sent by /sportsbooks — see the note on ``Sport`` (issue #23).
    slug: str | None = None
    # The wire carries availability as the STRING ``status`` ("active",
    # "outage", ...), not a boolean. ``active`` is derived from it below so
    # that existing ``book.active`` readers keep working.
    status: str | None = None
    active: bool | None = None
    coming_soon: bool | None = None
    category: str | None = None
    is_sharp: bool | None = None
    has_live_odds: bool | None = None
    has_player_props: bool | None = None
    requires_tier: str | None = None
    event_count: int | None = None
    last_update: str | None = None
    regions: list[str] | None = None
    features: list[str] | None = None
    # Optional integer numerical ID, additive.
    numerical_id: int | None = None

    model_config = {"populate_by_name": True, "extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def _derive_active_from_status(cls, data: Any) -> Any:
        """Populate ``active`` from the wire's ``status`` string.

        Only fills the gap — an explicit ``active`` in the payload wins, so
        this cannot mask a future wire change that starts sending both.
        """
        if isinstance(data, dict) and data.get("active") is None:
            status = data.get("status")
            if isinstance(status, str):
                data = {**data, "active": status.lower() == "active"}
        return data


class Team(BaseModel):
    """A team / competitor returned by the ``/teams`` reference endpoint.

    ``abbreviation`` is only present for ~1500 team-sport entities and is
    absent for individual-sport competitors.
    """

    id: str
    name: str | None = None
    sport: str | None = None
    league: str | None = None
    abbreviation: str | None = None
    numerical_id: int | None = None

    model_config = {"extra": "allow"}


class Event(BaseModel):
    id: str
    sport: str
    league: str
    home_team: str
    away_team: str
    start_time: str | None = None
    is_live: bool = False
    status: str | None = None
    # Optional structured refs (additive, non-breaking).
    home: TeamRef | None = None
    away: TeamRef | None = None
    sport_ref: SportRef | None = None
    league_ref: EntityRef | None = None


class Market(BaseModel):
    """A market available on an event."""

    market_type: str
    market_label: str | None = None
    selection_count: int | None = None
    book_count: int | None = None
    books: list[str] | None = None
    # Optional integer numerical ID, additive.
    numerical_id: int | None = None


# =============================================================================
# Closing Snapshot
# =============================================================================


class ClosingOddsLine(BaseModel):
    """A single closing-line odds entry within a closing snapshot."""

    sportsbook: str
    market_type: str
    selection: str
    selection_type: str | None = None
    # Structured side/segment axes (issue #76 / #689), additive + optional.
    team_side: str | None = None
    market_segment: str | None = None
    odds_american: int | float
    odds_decimal: float
    line: float | None = None
    player_name: str | None = None
    stat_category: str | None = None
    # Optional structured refs (additive, non-breaking).
    market_ref: EntityRef | None = None
    sportsbook_ref: EntityRef | None = None


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
    # Optional structured refs (additive, non-breaking).
    home: TeamRef | None = None
    away: TeamRef | None = None
    sport_ref: SportRef | None = None
    league_ref: EntityRef | None = None


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
    """Legacy shape of ``AccountInfo.features``.

    The wire moved to a flat list of feature names; this class is retained so
    imports of it keep resolving, but ``AccountInfo.features`` is now a
    ``list[str]``. See ``AccountInfo.has_feature``.
    """

    ev: bool = False
    arbitrage: bool = False
    middles: bool = False
    streaming: bool = False


class AccountStreaming(BaseModel):
    enabled: bool | None = None
    max_connections: int | None = None

    model_config = {"extra": "allow"}


class AccountInfo(BaseModel):
    key: dict[str, Any] | None = None
    key_id: str | None = None
    tier: str | None = None
    limits: AccountLimits | None = None
    # The wire calls the same block ``rate_limit``.
    rate_limit: AccountLimits | None = None
    # The wire sends a flat list of enabled feature names, e.g.
    # ``["odds", "ev", "arbitrage"]``. It was declared as an object of
    # booleans, which made every ``account.me()`` call raise (issue #23).
    features: list[str] = Field(default_factory=list)
    streaming: AccountStreaming | None = None
    add_ons: list[str] | None = None

    model_config = {"extra": "allow"}

    def has_feature(self, name: str) -> bool:
        """Whether ``name`` is enabled, replacing the old ``features.<name>``."""
        return name in self.features


class RateLimitInfo(BaseModel):
    """Rate limit state from response headers."""

    limit: int | None = None
    remaining: int | None = None
    reset: float | None = None
    tier: str | None = None
