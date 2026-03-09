"""Internal utilities."""

from __future__ import annotations


def american_to_decimal(american: int | float) -> float:
    """Convert American odds to decimal odds."""
    if american > 0:
        return american / 100 + 1
    return 100 / abs(american) + 1


def decimal_to_american(decimal: float) -> int:
    """Convert decimal odds to American odds."""
    if decimal >= 2.0:
        return round((decimal - 1) * 100)
    return round(-100 / (decimal - 1))


def american_to_probability(american: int | float) -> float:
    """Convert American odds to implied probability (0-1)."""
    if american > 0:
        return 100 / (american + 100)
    return abs(american) / (abs(american) + 100)


def _clean_params(params: dict) -> dict:
    """Remove None values and join lists with commas."""
    cleaned = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            cleaned[key] = str(value).lower()
        elif isinstance(value, list):
            cleaned[key] = ",".join(str(v) for v in value)
        else:
            cleaned[key] = value
    return cleaned
