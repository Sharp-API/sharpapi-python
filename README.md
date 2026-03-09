# SharpAPI Python SDK

Official Python client for the [SharpAPI](https://sharpapi.io) real-time sports betting odds API.

Get pre-computed +EV opportunities, arbitrage detection, middles, and live odds from 20+ sportsbooks — with Pinnacle as the sharp reference.

## Install

```bash
pip install sharpapi
```

## Quick Start

```python
from sharpapi import SharpAPI

client = SharpAPI("sk_live_xxx")

# --- Arbitrage opportunities ---
arbs = client.arbitrage.get(min_profit=1.0, league="nba")
for arb in arbs.data:
    print(f"{arb.profit_percent:.2f}% profit — {arb.event_name}")
    for leg in arb.legs:
        print(f"  {leg.sportsbook}: {leg.selection} @ {leg.odds_american} ({leg.stake_percent:.1f}%)")

# --- +EV opportunities ---
evs = client.ev.get(min_ev=3.0, sport="basketball")
for opp in evs.data:
    print(f"+{opp.ev_percent:.1f}% EV on {opp.selection} @ {opp.sportsbook}")
    if opp.kelly_fraction:
        print(f"  Kelly: {opp.kelly_fraction:.1%} of bankroll")

# --- Best odds across books ---
odds = client.odds.best(league="nba", market="moneyline")
for line in odds.data:
    print(f"{line.home_team} vs {line.away_team}: {line.selection} {line.odds_american}")
```

## Streaming

Real-time SSE streaming for odds updates and opportunity alerts (requires WebSocket add-on):

```python
stream = client.stream.opportunities(league="nba")

@stream.on("ev:detected")
def on_ev(data):
    for opp in data:
        print(f"+EV: {opp['selection']} {opp['ev_percent']}% @ {opp['sportsbook']}")

@stream.on("arb:detected")
def on_arb(data):
    for arb in data:
        print(f"Arb: {arb['profit_percent']}% — {arb['event_name']}")

stream.connect()  # Blocks, processing events
```

Or iterate over events:

```python
for event_type, data in stream.iter_events():
    if event_type == "ev:detected":
        print(data)
```

## All Resources

```python
# Odds
client.odds.get(sport="basketball", league="nba")
client.odds.best(league="nfl", market="moneyline")
client.odds.comparison(event_id="abc123")
client.odds.batch(event_ids=["abc123", "def456"])

# Opportunities
client.ev.get(min_ev=2.0, sportsbook="draftkings")
client.arbitrage.get(min_profit=0.5, sport="football")
client.middles.get(sport="football", min_size=3.0)
client.low_hold.get(max_hold=2.0)

# Reference data
client.sports.list()
client.leagues.list(sport="basketball")
client.sportsbooks.list()
client.events.list(league="nba", live=True)
client.events.search("Lakers")

# Account
client.account.me()       # Tier, limits, features
client.account.usage()    # Request counts

# Streaming
client.stream.odds(league="nba")
client.stream.opportunities(min_ev=3.0)
client.stream.all(sport="basketball")
client.stream.event("event_id_here")
```

## Data Quality

Every opportunity response includes staleness metadata to avoid acting on stale odds:

```python
arbs = client.arbitrage.get()
for arb in arbs.data:
    if arb.possibly_stale:
        print(f"  Skipping — odds may be stale ({arb.oldest_odds_age_seconds}s old)")
        continue
    if "LIVE_HIGH_PROFIT_SUSPICIOUS" in arb.warnings:
        print(f"  Skipping — likely phantom arb")
        continue
    print(f"Actionable: {arb.profit_percent}%")
```

## Rate Limits

Rate limit info is available after every request:

```python
response = client.odds.get()
print(f"Remaining: {client.rate_limit.remaining}/{client.rate_limit.limit}")
print(f"Tier: {client.rate_limit.tier}")
```

## Error Handling

```python
from sharpapi import (
    SharpAPI,
    AuthenticationError,
    TierRestrictedError,
    RateLimitedError,
)

client = SharpAPI("sk_live_xxx")

try:
    evs = client.ev.get()
except AuthenticationError:
    print("Invalid API key")
except TierRestrictedError as e:
    print(f"Upgrade to {e.required_tier} tier for this feature")
except RateLimitedError as e:
    print(f"Rate limited — retry after {e.retry_after}s")
```

## Odds Conversion Utilities

```python
from sharpapi import american_to_decimal, american_to_probability, decimal_to_american

american_to_decimal(-110)       # 1.909
american_to_decimal(150)        # 2.5
american_to_probability(-110)   # 0.524
decimal_to_american(2.5)        # 150
```

## Requirements

- Python 3.9+
- httpx
- pydantic v2

## Links

- [API Docs](https://docs.sharpapi.io)
- [Dashboard](https://sharpapi.io/dashboard)
- [Discord](https://discord.gg/sharpapi)
