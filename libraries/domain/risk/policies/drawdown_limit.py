"""Drawdown Limit Risk Policy."""

from decimal import Decimal
from typing import Any, Dict

from libraries.domain.risk.models import PolicyResult
from libraries.domain.risk.policies.base import BaseRiskPolicy
from libraries.domain.risk.types import PolicyStatus


class DrawdownLimitPolicy(BaseRiskPolicy):
    """Enforces maximum allowable drawdown limit."""

    def __init__(
        self,
        name: str = "drawdown_limit",
        enabled: bool = True,
        max_drawdown: Decimal = Decimal("0.10"),
    ) -> None:
        super().__init__(name=name, enabled=enabled)
        self.max_drawdown: Decimal = max_drawdown

    async def evaluate(self, context: Dict[str, Any]) -> PolicyResult:
        """Evaluate maximum drawdown against limit."""
        if not self.enabled:
            return PolicyResult(
                policy_name=self.name,
                status=PolicyStatus.PASSED,
                message="Drawdown limit policy disabled",
                passed=True,
            )

        current_dd: Decimal = context.get("current_drawdown", Decimal("0"))
        if current_dd > self.max_drawdown:
            return PolicyResult(
                policy_name=self.name,
                status=PolicyStatus.REJECTED,
                message=f"Drawdown {current_dd} exceeds maximum limit {self.max_drawdown}",
                passed=False,
            )

        return PolicyResult(
            policy_name=self.name,
            status=PolicyStatus.PASSED,
            message="Drawdown within limits",
            passed=True,
        )
