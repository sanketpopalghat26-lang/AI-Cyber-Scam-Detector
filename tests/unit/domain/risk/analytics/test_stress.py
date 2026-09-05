"""Unit tests for Stress Testing Engine with 13 async test methods properly decorated."""

from decimal import Decimal
import pytest

from libraries.domain.risk.analytics.stress import StressTestEngine
from libraries.domain.risk.models import StressResult, StressScenario
from libraries.domain.risk.types import StressSeverity


@pytest.fixture
def stress_engine() -> StressTestEngine:
    return StressTestEngine()


@pytest.mark.asyncio
async def test_stress_single_scenario(stress_engine: StressTestEngine, sample_stress_scenario: StressScenario) -> None:
    positions = {"EURUSD": Decimal("100000.0")}
    result = await stress_engine.run_scenario(Decimal("100000.0"), positions, sample_stress_scenario)
    assert isinstance(result, StressResult)
    assert result.estimated_loss == Decimal("10000.0")


@pytest.mark.asyncio
async def test_stress_multiple_positions(stress_engine: StressTestEngine, sample_stress_scenario: StressScenario) -> None:
    positions = {
        "EURUSD": Decimal("100000.0"),
        "GBPUSD": Decimal("50000.0"),
    }
    result = await stress_engine.run_scenario(Decimal("100000.0"), positions, sample_stress_scenario)
    assert result.estimated_loss == Decimal("17500.0")


@pytest.mark.asyncio
async def test_stress_default_shock(stress_engine: StressTestEngine, sample_stress_scenario: StressScenario) -> None:
    positions = {"USDJPY": Decimal("100000.0")}
    result = await stress_engine.run_scenario(Decimal("100000.0"), positions, sample_stress_scenario)
    assert result.estimated_loss == Decimal("5000.0")


@pytest.mark.asyncio
async def test_stress_multiple_scenarios_concurrently(stress_engine: StressTestEngine, sample_stress_scenario: StressScenario) -> None:
    positions = {"EURUSD": Decimal("100000.0")}
    scenarios = [sample_stress_scenario, sample_stress_scenario]
    results = await stress_engine.run_scenarios(Decimal("100000.0"), positions, scenarios)
    assert len(results) == 2


@pytest.mark.asyncio
async def test_stress_zero_portfolio_value(stress_engine: StressTestEngine, sample_stress_scenario: StressScenario) -> None:
    result = await stress_engine.run_scenario(Decimal("0.0"), {}, sample_stress_scenario)
    assert result.estimated_loss == Decimal("0")
    assert result.loss_percentage == Decimal("0")


@pytest.mark.asyncio
async def test_stress_capital_remaining_calculation(stress_engine: StressTestEngine, sample_stress_scenario: StressScenario) -> None:
    positions = {"EURUSD": Decimal("100000.0")}
    result = await stress_engine.run_scenario(Decimal("100000.0"), positions, sample_stress_scenario)
    assert result.capital_remaining == Decimal("90000.0")


@pytest.mark.asyncio
async def test_stress_acceptability_threshold_pass(stress_engine: StressTestEngine) -> None:
    mild_scenario = StressScenario(
        scenario_id="MILD_DIP",
        name="Mild Dip",
        description="Small market movement",
        severity=StressSeverity.MILD,
        shocks={"EURUSD": Decimal("0.02")},
    )
    result = await stress_engine.run_scenario(Decimal("100000.0"), {"EURUSD": Decimal("100000.0")}, mild_scenario)
    assert result.is_acceptable is True


@pytest.mark.asyncio
async def test_stress_acceptability_threshold_fail(stress_engine: StressTestEngine) -> None:
    severe_scenario = StressScenario(
        scenario_id="CRASH",
        name="Crash",
        description="Heavy market drop",
        severity=StressSeverity.MODERATE,
        shocks={"EURUSD": Decimal("0.25")},
    )
    result = await stress_engine.run_scenario(Decimal("100000.0"), {"EURUSD": Decimal("100000.0")}, severe_scenario)
    assert result.is_acceptable is False


@pytest.mark.asyncio
async def test_stress_negative_position_value(stress_engine: StressTestEngine, sample_stress_scenario: StressScenario) -> None:
    positions = {"EURUSD": Decimal("-50000.0")}
    result = await stress_engine.run_scenario(Decimal("100000.0"), positions, sample_stress_scenario)
    assert isinstance(result, StressResult)


@pytest.mark.asyncio
async def test_stress_empty_positions(stress_engine: StressTestEngine, sample_stress_scenario: StressScenario) -> None:
    result = await stress_engine.run_scenario(Decimal("100000.0"), {}, sample_stress_scenario)
    assert result.estimated_loss == Decimal("0")


@pytest.mark.asyncio
async def test_stress_extreme_severity_threshold(stress_engine: StressTestEngine, sample_stress_scenario: StressScenario) -> None:
    positions = {"EURUSD": Decimal("150000.0")}
    result = await stress_engine.run_scenario(Decimal("100000.0"), positions, sample_stress_scenario)
    # loss pct 15% <= 20% extreme threshold -> True
    assert result.is_acceptable is True


@pytest.mark.asyncio
async def test_stress_extreme_severity_threshold_fail(stress_engine: StressTestEngine, sample_stress_scenario: StressScenario) -> None:
    positions = {"EURUSD": Decimal("250000.0")}
    result = await stress_engine.run_scenario(Decimal("100000.0"), positions, sample_stress_scenario)
    # loss pct 25% > 20% extreme threshold -> False
    assert result.is_acceptable is False


@pytest.mark.asyncio
async def test_stress_scenario_name_preservation(stress_engine: StressTestEngine, sample_stress_scenario: StressScenario) -> None:
    result = await stress_engine.run_scenario(Decimal("100000.0"), {}, sample_stress_scenario)
    assert result.scenario_name == "2008 Financial Crisis"
