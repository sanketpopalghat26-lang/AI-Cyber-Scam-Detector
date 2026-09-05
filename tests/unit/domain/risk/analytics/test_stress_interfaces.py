"""Unit tests for Stress Testing interface contracts."""

from decimal import Decimal
import pytest

from libraries.domain.risk.analytics.stress import StressTestEngine
from libraries.domain.risk.models import StressScenario
from libraries.domain.risk.ports import StressTestPort
from libraries.domain.risk.types import StressSeverity


@pytest.mark.asyncio
async def test_stress_test_port_conformance() -> None:
    engine = StressTestEngine()
    assert isinstance(engine, StressTestPort)


@pytest.mark.asyncio
async def test_stress_test_interface_execution() -> None:
    engine: StressTestPort = StressTestEngine()
    scenario = StressScenario(
        scenario_id="TEST",
        name="Test Scenario",
        description="Test description",
        severity=StressSeverity.MILD,
        shocks={"EURUSD": Decimal("0.05")},
    )
    result = await engine.run_scenario(Decimal("100000.0"), {"EURUSD": Decimal("10000.0")}, scenario)
    assert result.scenario_id == "TEST"
