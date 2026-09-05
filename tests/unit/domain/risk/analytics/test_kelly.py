"""Unit tests for Kelly Criterion position sizing."""

from decimal import Decimal
from libraries.domain.risk.analytics.kelly import calculate_kelly_fraction


def test_kelly_positive() -> None:
    kelly = calculate_kelly_fraction(Decimal("0.60"), Decimal("1.5"))
    assert isinstance(kelly, Decimal)
    assert kelly > Decimal("0")


def test_kelly_negative() -> None:
    kelly = calculate_kelly_fraction(Decimal("0.30"), Decimal("1.0"))
    assert kelly == Decimal("0")
