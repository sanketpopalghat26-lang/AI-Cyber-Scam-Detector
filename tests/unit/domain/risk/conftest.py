"""Pytest fixtures for Risk Domain unit tests."""

from decimal import Decimal
import pytest

from libraries.domain.risk.models import StressScenario
from libraries.domain.risk.types import StressSeverity


@pytest.fixture
def sample_returns() -> list[Decimal]:
    """Sample historical returns sequence for VaR/CVaR/Ratio testing."""
    return [
        Decimal("0.01"),
        Decimal("-0.02"),
        Decimal("0.015"),
        Decimal("-0.01"),
        Decimal("0.005"),
        Decimal("-0.03"),
        Decimal("0.02"),
        Decimal("-0.005"),
        Decimal("0.01"),
        Decimal("-0.015"),
    ]


@pytest.fixture
def sample_equity_curve() -> list[Decimal]:
    """Sample account equity curve."""
    return [
        Decimal("100000.0"),
        Decimal("102000.0"),
        Decimal("105000.0"),
        Decimal("101000.0"),
        Decimal("98000.0"),
        Decimal("103000.0"),
    ]


@pytest.fixture
def sample_stress_scenario() -> StressScenario:
    """Sample stress testing scenario."""
    return StressScenario(
        scenario_id="CRASH_2008",
        name="2008 Financial Crisis",
        description="Market crash scenario with high asset correlation and volatility",
        severity=StressSeverity.EXTREME,
        shocks={
            "EURUSD": Decimal("0.10"),
            "GBPUSD": Decimal("0.15"),
            "DEFAULT": Decimal("0.05"),
        },
    )
