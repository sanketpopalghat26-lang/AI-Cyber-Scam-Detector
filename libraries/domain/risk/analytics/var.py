"""Value at Risk (VaR) calculations using Decimal."""

import math
from decimal import Decimal
from typing import Sequence


def calculate_historical_var(
    returns: Sequence[Decimal],
    confidence_level: Decimal = Decimal("0.95"),
    portfolio_value: Decimal = Decimal("1.0"),
) -> Decimal:
    """Calculate Historical Value at Risk (VaR).

    Args:
        returns: Sequence of historical period returns as Decimal.
        confidence_level: Confidence level e.g. 0.95 for 95% VaR.
        portfolio_value: Total portfolio value.

    Returns:
        Estimated VaR as a positive Decimal amount.
    """
    if not returns:
        return Decimal("0")

    sorted_returns = sorted(returns)
    index = int((Decimal("1.0") - confidence_level) * Decimal(str(len(sorted_returns))))
    index = max(0, min(index, len(sorted_returns) - 1))
    cutoff_return = sorted_returns[index]

    if cutoff_return >= Decimal("0"):
        return Decimal("0")

    return abs(cutoff_return) * portfolio_value


def calculate_parametric_var(
    returns: Sequence[Decimal],
    confidence_level: Decimal = Decimal("0.95"),
    portfolio_value: Decimal = Decimal("1.0"),
) -> Decimal:
    """Calculate Parametric (Variance-Covariance) Value at Risk under normality assumption."""
    if not returns or len(returns) < 2:
        return Decimal("0")

    n = Decimal(str(len(returns)))
    mean = sum(returns, Decimal("0")) / n
    variance = sum((r - mean) ** Decimal("2") for r in returns) / (n - Decimal("1"))
    std_dev = Decimal(str(math.sqrt(float(variance))))

    # Normal distribution Z-score approximation
    if confidence_level == Decimal("0.99"):
        z_score = Decimal("2.326")
    elif confidence_level == Decimal("0.95"):
        z_score = Decimal("1.645")
    else:
        z_score = Decimal("1.645")

    var_pct = (z_score * std_dev) - mean
    if var_pct <= Decimal("0"):
        return Decimal("0")

    return var_pct * portfolio_value
