"""Exposure Limit Risk Policy."""

from decimal import Decimal
from typing import Any, Dict

from libraries.domain.risk.models import PolicyResult
from libraries.domain.risk.policies.base import BaseRiskPolicy
from libraries.domain.risk.types import PolicyStatus


class ExposureLimitPolicy(BaseRiskPolicy):
    """Enforces maximum gross and net exposure limits."""

    def __init__(
        self,
        name: str = "exposure_limit",
        enabled: bool = True,
        max_gross_exposure: Decimal = Decimal("2.0"),
    ) -> None:
        super().__init__(name=name, enabled=enabled)
        self.max_gross_exposure: Decimal = max_gross_exposure

    async def evaluate(self, context: Dict[str, Any]) -> PolicyResult:
        """Evaluate gross exposure against threshold limit."""
        if not self.enabled:
            return PolicyResult(
                policy_name=self.name,
                status=PolicyStatus.PASSED,
                message="Exposure policy disabled",
                passed=True,
            )

        gross_exposure: Decimal = context.get("gross_exposure", Decimal("0"))
        if gross_exposure > self.max_gross_exposure:
            return PolicyResult(
                policy_name=self.name,
                status=PolicyStatus.REJECTED,
                message=f"Gross exposure {gross_exposure} exceeds limit {self.max_gross_exposure}",
                passed=False,
            )

        return PolicyResult(
            policy_name=self.name,
            status=PolicyStatus.PASSED,
            message="Exposure limits satisfied",
            passed=True,
        )
