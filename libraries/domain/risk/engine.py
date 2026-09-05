"""Risk Engine for concurrent evaluation of risk policies using asyncio.TaskGroup."""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List

from libraries.domain.risk.models import PolicyEvaluation, PolicyResult
from libraries.domain.risk.ports import RiskEnginePort, RiskPolicyPort


class RiskEngine(RiskEnginePort):
    """Orchestrates policy evaluations concurrently."""

    def __init__(self, policies: List[RiskPolicyPort] | None = None) -> None:
        self.policies: List[RiskPolicyPort] = policies if policies is not None else []

    def register_policy(self, policy: RiskPolicyPort) -> None:
        """Register a risk policy."""
        self.policies.append(policy)

    async def evaluate_policies(self, context: Dict[str, Any]) -> PolicyEvaluation:
        """Evaluate registered policies concurrently using asyncio.TaskGroup.

        Guarantees that policy-result collection occurs ONLY AFTER TaskGroup tasks complete.
        """
        if not self.policies:
            return PolicyEvaluation(
                timestamp=datetime.now(timezone.utc),
                overall_passed=True,
                results=[],
                recommended_scale=Decimal("1.0"),
            )

        tasks: List[asyncio.Task[PolicyResult]] = []
        async with asyncio.TaskGroup() as tg:
            for policy in self.policies:
                task = tg.create_task(policy.evaluate(context))
                tasks.append(task)

        # Collection occurs strictly after TaskGroup completion
        results: List[PolicyResult] = [task.result() for task in tasks]

        overall_passed = all(res.passed for res in results)
        scale_factors = [
            res.position_scale_factor
            for res in results
            if res.position_scale_factor is not None
        ]
        recommended_scale = min(scale_factors) if scale_factors else Decimal("1.0")

        return PolicyEvaluation(
            timestamp=datetime.now(timezone.utc),
            overall_passed=overall_passed,
            results=results,
            recommended_scale=recommended_scale,
        )
