"""SharpAPI Python SDK — Real-time sports betting odds, +EV, and arbitrage detection.

Example::

    from sharpapi import SharpAPI

    client = SharpAPI("sk_live_xxx")

    # Arbitrage opportunities
    arbs = client.arbitrage.get(min_profit=1.0)
    for arb in arbs.data:
        print(f"{arb.profit_percent}% — {arb.event_name}")

    # +EV opportunities
    evs = client.ev.get(min_ev=3.0, league="nba")
    for opp in evs.data:
        print(f"+{opp.ev_percentage}% on {opp.selection} @ {opp.sportsbook}")
"""

from ._utils import american_to_decimal, american_to_probability, decimal_to_american
from .async_client import AsyncSharpAPI
from .client import SharpAPI
from .exceptions import (
    ERROR_CODE_DESCRIPTIONS,
    ERROR_CODE_TO_EXCEPTION,
    AuthenticationError,
    RateLimitedError,
    SharpAPIError,
    StreamError,
    TierRestrictedError,
    ValidationError,
)
from .models import (
    AccountInfo,
    APIKey,
    APIResponse,
    ArbitrageLeg,
    ArbitrageOpportunity,
    ClosingOddsLine,
    ClosingSnapshot,
    Event,
    EVOpportunity,
    GameState,
    League,
    LowHoldOpportunity,
    LowHoldSide,
    Market,
    MiddleOpportunity,
    MiddleSide,
    OddsLine,
    OddsValue,
    Pagination,
    RateLimitInfo,
    ResponseMeta,
    Sport,
    Sportsbook,
)
from .streaming import EventStream

__version__ = "0.3.0"

__all__ = [
    # Clients
    "SharpAPI",
    "AsyncSharpAPI",
    # Models
    "APIKey",
    "APIResponse",
    "AccountInfo",
    "ArbitrageLeg",
    "ArbitrageOpportunity",
    "ClosingOddsLine",
    "ClosingSnapshot",
    "EVOpportunity",
    "Event",
    "GameState",
    "League",
    "LowHoldOpportunity",
    "LowHoldSide",
    "Market",
    "MiddleOpportunity",
    "MiddleSide",
    "OddsLine",
    "OddsValue",
    "Pagination",
    "RateLimitInfo",
    "ResponseMeta",
    "Sport",
    "Sportsbook",
    # Streaming
    "EventStream",
    # Exceptions
    "AuthenticationError",
    "RateLimitedError",
    "SharpAPIError",
    "StreamError",
    "TierRestrictedError",
    "ValidationError",
    # Error-code registry
    "ERROR_CODE_DESCRIPTIONS",
    "ERROR_CODE_TO_EXCEPTION",
    # Utilities
    "american_to_decimal",
    "american_to_probability",
    "decimal_to_american",
]
