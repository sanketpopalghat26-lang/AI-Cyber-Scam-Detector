"""Risk-adjusted performance ratios (Sharpe, Sortino, Calmar) using Decimal."""

import math
from decimal import Decimal
from typing import Sequence


def calculate_sharpe_ratio(
    returns: Sequence[Decimal],
    risk_free_rate: Decimal = Decimal("0.0"),
    annualization_factor: Decimal = Decimal("252.0"),
) -> Decimal:
    """Calculate annualized Sharpe Ratio."""
    if not returns or len(returns) < 2:
        return Decimal("0")

    n = Decimal(str(len(returns)))
    mean_return = sum(returns, Decimal("0")) / n
    excess_return = mean_return - (risk_free_rate / annualization_factor)

    variance = sum((r - mean_return) ** Decimal("2") for r in returns) / (n - Decimal("1"))
    if variance <= Decimal("0"):
        return Decimal("0")

    std_dev = Decimal(str(math.sqrt(float(variance))))
    annualized_factor = Decimal(str(math.sqrt(float(annualization_factor))))

    return (excess_return / std_dev) * annualized_factor


def calculate_sortino_ratio(
    returns: Sequence[Decimal],
    target_return: Decimal = Decimal("0.0"),
    annualization_factor: Decimal = Decimal("252.0"),
) -> Decimal:
    """Calculate annualized Sortino Ratio focusing on downside volatility."""
    if not returns or len(returns) < 2:
        return Decimal("0")

    n = Decimal(str(len(returns)))
    mean_return = sum(returns, Decimal("0")) / n
    excess_return = mean_return - (target_return / annualization_factor)

    downside_diffs = [min(Decimal("0"), r - target_return) for r in returns]
    downside_variance = sum(d ** Decimal("2") for d in downside_diffs) / n

    if downside_variance <= Decimal("0"):
        return Decimal("0")

    downside_dev = Decimal(str(math.sqrt(float(downside_variance))))
    annualized_factor = Decimal(str(math.sqrt(float(annualization_factor))))

    return (excess_return / downside_dev) * annualized_factor


def calculate_calmar_ratio(
    total_return: Decimal,
    max_drawdown: Decimal,
) -> Decimal:
    """Calculate Calmar Ratio (Annualized Return / Max Drawdown)."""
    if max_drawdown <= Decimal("0"):
        return Decimal("0")

    return total_return / abs(max_drawdown)
