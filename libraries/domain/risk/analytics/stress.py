"""Async Stress Testing Engine for historical and hypothetical scenario evaluation."""

import asyncio
from decimal import Decimal
from typing import Dict, Sequence

from libraries.domain.risk.models import StressResult, StressScenario
from libraries.domain.risk.ports import StressTestPort
from libraries.domain.risk.types import StressSeverity


class StressTestEngine(StressTestPort):
    """Async stress test simulator."""

    async def run_scenario(
        self,
        portfolio_value: Decimal,
        positions: Dict[str, Decimal],
        scenario: StressScenario,
    ) -> StressResult:
        """Evaluate a stress scenario asynchronously against portfolio positions."""
        await asyncio.sleep(0.001)  # Async yield

        total_loss = Decimal("0")
        for symbol, pos_val in positions.items():
            shock = scenario.shocks.get(symbol, scenario.shocks.get("DEFAULT", Decimal("0")))
            loss = pos_val * shock
            total_loss += loss

        loss_pct = (total_loss / portfolio_value) if portfolio_value > Decimal("0") else Decimal("0")
        capital_remaining = portfolio_value - total_loss

        # Acceptability threshold depends on severity
        threshold = Decimal("0.20") if scenario.severity == StressSeverity.EXTREME else Decimal("0.10")
        is_acceptable = loss_pct <= threshold

        return StressResult(
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.name,
            estimated_loss=total_loss,
            loss_percentage=loss_pct,
            capital_remaining=capital_remaining,
            is_acceptable=is_acceptable,
        )

    async def run_scenarios(
        self,
        portfolio_value: Decimal,
        positions: Dict[str, Decimal],
        scenarios: Sequence[StressScenario],
    ) -> Sequence[StressResult]:
        """Run multiple stress test scenarios concurrently."""
        tasks = [self.run_scenario(portfolio_value, positions, sc) for sc in scenarios]
        return await asyncio.gather(*tasks)
