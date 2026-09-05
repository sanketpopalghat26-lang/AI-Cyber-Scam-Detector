"""Kelly Criterion optimal position sizing using Decimal."""

from decimal import Decimal


def calculate_kelly_fraction(
    win_rate: Decimal,
    win_loss_ratio: Decimal,
    fraction_multiplier: Decimal = Decimal("1.0"),
) -> Decimal:
    """Calculate Kelly Criterion fraction for optimal capital allocation.

    Formula: f* = (p * b - q) / b
    where p = win rate, q = loss rate (1-p), b = win/loss ratio.
    """
    if win_rate <= Decimal("0") or win_rate >= Decimal("1.0"):
        return Decimal("0")
    if win_loss_ratio <= Decimal("0"):
        return Decimal("0")

    p = win_rate
    q = Decimal("1.0") - p
    b = win_loss_ratio

    full_kelly = (p * b - q) / b
    if full_kelly <= Decimal("0"):
        return Decimal("0")

    return full_kelly * fraction_multiplier
