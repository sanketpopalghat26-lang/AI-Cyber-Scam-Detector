"""Unit tests for Gross and Net Exposure analytics."""

from decimal import Decimal
from libraries.domain.risk.analytics.exposure import calculate_exposure


def test_exposure_calculation() -> None:
    positions = {
        "EURUSD": Decimal("50000.0"),
        "GBPUSD": Decimal("-30000.0"),
    }
    capital = Decimal("100000.0")

    gross, net, leverage = calculate_exposure(positions, capital)
    assert gross == Decimal("80000.0")
    assert net == Decimal("20000.0")
    assert leverage == Decimal("0.8")
