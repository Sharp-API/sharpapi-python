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
        print(f"+{opp.ev_percent}% on {opp.selection} @ {opp.sportsbook}")
"""

from .async_client import AsyncSharpAPI
from .client import SharpAPI
from .exceptions import (
    AuthenticationError,
    RateLimitedError,
    SharpAPIError,
    StreamError,
    TierRestrictedError,
    ValidationError,
)
from .models import (
    APIResponse,
    AccountInfo,
    ArbitrageLeg,
    ArbitrageOpportunity,
    EVOpportunity,
    Event,
    GameState,
    League,
    LowHoldOpportunity,
    LowHoldSide,
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
from ._utils import american_to_decimal, american_to_probability, decimal_to_american

__version__ = "0.1.0"

__all__ = [
    # Clients
    "SharpAPI",
    "AsyncSharpAPI",
    # Models
    "APIResponse",
    "AccountInfo",
    "ArbitrageLeg",
    "ArbitrageOpportunity",
    "EVOpportunity",
    "Event",
    "GameState",
    "League",
    "LowHoldOpportunity",
    "LowHoldSide",
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
    # Utilities
    "american_to_decimal",
    "american_to_probability",
    "decimal_to_american",
]
