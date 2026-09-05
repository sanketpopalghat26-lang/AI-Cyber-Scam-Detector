"""Recovery Mode Risk Policy."""

from decimal import Decimal
from typing import Any, Dict

from libraries.domain.risk.models import PolicyResult
from libraries.domain.risk.policies.base import BaseRiskPolicy
from libraries.domain.risk.types import PolicyStatus


class RecoveryModePolicy(BaseRiskPolicy):
    """Adjusts position sizing or blocks trading during drawdown recovery phases."""

    def __init__(
        self,
        name: str = "recovery_mode",
        enabled: bool = True,
        recovery_scale_factor: Decimal = Decimal("0.5"),
        max_recovery_drawdown: Decimal = Decimal("0.15"),
        is_blocking_gate: bool = False,
    ) -> None:
        super().__init__(name=name, enabled=enabled)
        self.recovery_scale_factor: Decimal = recovery_scale_factor
        self.max_recovery_drawdown: Decimal = max_recovery_drawdown
        self.is_blocking_gate: bool = is_blocking_gate

    async def evaluate(self, context: Dict[str, Any]) -> PolicyResult:
        """Evaluate recovery mode state."""
        if not self.enabled:
            return PolicyResult(
                policy_name=self.name,
                status=PolicyStatus.PASSED,
                message="Recovery mode policy disabled",
                passed=True,
            )

        in_recovery: bool = context.get("in_recovery_mode", False)
        current_drawdown: Decimal = context.get("current_drawdown", Decimal("0"))
        strict_reject: bool = context.get("strict_blocking", False) or self.is_blocking_gate

        if in_recovery or current_drawdown >= self.max_recovery_drawdown:
            if strict_reject:
                return PolicyResult(
                    policy_name=self.name,
                    status=PolicyStatus.REJECTED,
                    message=f"Recovery mode active: Drawdown {current_drawdown} exceeds threshold",
                    passed=False,
                    position_scale_factor=Decimal("0.0"),
                )

            return PolicyResult(
                policy_name=self.name,
                status=PolicyStatus.INFORMATIONAL,
                message=f"Recovery mode active: Position size scaled by {self.recovery_scale_factor}",
                passed=True,
                position_scale_factor=self.recovery_scale_factor,
            )

        return PolicyResult(
            policy_name=self.name,
            status=PolicyStatus.PASSED,
            message="Normal mode (not in recovery)",
            passed=True,
            position_scale_factor=Decimal("1.0"),
        )
