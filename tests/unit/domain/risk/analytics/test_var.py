"""Unit tests for Value at Risk (VaR) calculations."""

from decimal import Decimal
from libraries.domain.risk.analytics.var import calculate_historical_var, calculate_parametric_var


def test_historical_var(sample_returns: list[Decimal]) -> None:
    var_95 = calculate_historical_var(sample_returns, Decimal("0.95"), Decimal("100000.0"))
    assert isinstance(var_95, Decimal)
    assert var_95 >= Decimal("0")


def test_historical_var_empty() -> None:
    assert calculate_historical_var([], Decimal("0.95")) == Decimal("0")


def test_parametric_var(sample_returns: list[Decimal]) -> None:
    var_95 = calculate_parametric_var(sample_returns, Decimal("0.95"), Decimal("100000.0"))
    assert isinstance(var_95, Decimal)
    assert var_95 >= Decimal("0")
