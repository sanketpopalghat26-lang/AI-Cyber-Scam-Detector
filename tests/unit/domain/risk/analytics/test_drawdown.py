"""Unit tests for Drawdown analytics."""

from decimal import Decimal
from libraries.domain.risk.analytics.drawdown import calculate_drawdown


def test_drawdown_calculation(sample_equity_curve: list[Decimal]) -> None:
    max_dd, current_dd = calculate_drawdown(sample_equity_curve)
    assert isinstance(max_dd, Decimal)
    assert isinstance(current_dd, Decimal)
    assert max_dd >= Decimal("0")
    assert current_dd >= Decimal("0")


def test_drawdown_empty() -> None:
    max_dd, current_dd = calculate_drawdown([])
    assert max_dd == Decimal("0")
    assert current_dd == Decimal("0")
