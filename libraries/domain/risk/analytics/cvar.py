"""Conditional Value at Risk (CVaR / Expected Shortfall) using Decimal."""

from decimal import Decimal
from typing import Sequence


def calculate_cvar(
    returns: Sequence[Decimal],
    confidence_level: Decimal = Decimal("0.95"),
    portfolio_value: Decimal = Decimal("1.0"),
) -> Decimal:
    """Calculate Conditional Value at Risk (CVaR / Expected Shortfall).

    CVaR measures the expected loss given that loss exceeds the VaR threshold.
    """
    if not returns:
        return Decimal("0")

    sorted_returns = sorted(returns)
    cutoff_index = int((Decimal("1.0") - confidence_level) * Decimal(str(len(sorted_returns))))
    cutoff_index = max(1, min(cutoff_index, len(sorted_returns)))

    tail_returns = sorted_returns[:cutoff_index]
    if not tail_returns:
        return Decimal("0")

    avg_tail_loss = sum(tail_returns, Decimal("0")) / Decimal(str(len(tail_returns)))
    if avg_tail_loss >= Decimal("0"):
        return Decimal("0")

    return abs(avg_tail_loss) * portfolio_value
