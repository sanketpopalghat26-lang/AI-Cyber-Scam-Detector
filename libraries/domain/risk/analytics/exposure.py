"""Gross and Net Exposure analytics using Decimal."""

from decimal import Decimal
from typing import Dict, Tuple


def calculate_exposure(
    positions: Dict[str, Decimal],
    total_capital: Decimal,
) -> Tuple[Decimal, Decimal, Decimal]:
    """Calculate Gross Exposure, Net Exposure, and Leverage ratio.

    Args:
        positions: Map of symbol to position value (positive for long, negative for short).
        total_capital: Account equity capital.

    Returns:
        (gross_exposure, net_exposure, leverage) as Decimals.
    """
    if not positions or total_capital <= Decimal("0"):
        return Decimal("0"), Decimal("0"), Decimal("0")

    gross = sum((abs(val) for val in positions.values()), Decimal("0"))
    net = sum(positions.values(), Decimal("0"))
    leverage = gross / total_capital

    return gross, net, leverage
