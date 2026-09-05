"""Drawdown analytics using Decimal."""

from decimal import Decimal
from typing import Sequence, Tuple


def calculate_drawdown(
    equity_curve: Sequence[Decimal],
) -> Tuple[Decimal, Decimal]:
    """Calculate maximum drawdown percentage and current drawdown percentage.

    Returns:
        (max_drawdown, current_drawdown) as positive Decimal percentages.
    """
    if not equity_curve:
        return Decimal("0"), Decimal("0")

    peak = equity_curve[0]
    max_dd = Decimal("0")

    for value in equity_curve:
        if value > peak:
            peak = value
        elif peak > Decimal("0"):
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd

    current_peak = max(equity_curve) if equity_curve else Decimal("0")
    latest_value = equity_curve[-1] if equity_curve else Decimal("0")

    current_dd = (
        (current_peak - latest_value) / current_peak
        if current_peak > Decimal("0")
        else Decimal("0")
    )

    return max_dd, current_dd
