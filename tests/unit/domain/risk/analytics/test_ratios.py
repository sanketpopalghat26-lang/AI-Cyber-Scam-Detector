"""Unit tests for Sharpe, Sortino, and Calmar ratios."""

from decimal import Decimal
from libraries.domain.risk.analytics.ratios import calculate_calmar_ratio, calculate_sharpe_ratio, calculate_sortino_ratio


def test_sharpe_ratio(sample_returns: list[Decimal]) -> None:
    sharpe = calculate_sharpe_ratio(sample_returns)
    assert isinstance(sharpe, Decimal)


def test_sortino_ratio(sample_returns: list[Decimal]) -> None:
    sortino = calculate_sortino_ratio(sample_returns)
    assert isinstance(sortino, Decimal)


def test_calmar_ratio() -> None:
    calmar = calculate_calmar_ratio(Decimal("0.15"), Decimal("0.05"))
    assert calmar == Decimal("3.0")
