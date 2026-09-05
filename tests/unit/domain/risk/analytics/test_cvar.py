"""Unit tests for Conditional Value at Risk (CVaR)."""

from decimal import Decimal
from libraries.domain.risk.analytics.cvar import calculate_cvar


def test_cvar_calculation(sample_returns: list[Decimal]) -> None:
    cvar = calculate_cvar(sample_returns, Decimal("0.95"), Decimal("100000.0"))
    assert isinstance(cvar, Decimal)
    assert cvar >= Decimal("0")


def test_cvar_empty_returns() -> None:
    assert calculate_cvar([], Decimal("0.95")) == Decimal("0")
