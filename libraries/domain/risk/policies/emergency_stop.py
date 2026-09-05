"""Emergency Stop Risk Policy."""

from typing import Any, Dict, List

from libraries.domain.risk.models import PolicyResult
from libraries.domain.risk.policies.base import BaseRiskPolicy
from libraries.domain.risk.types import PolicyStatus


class EmergencyStopPolicy(BaseRiskPolicy):
    """Halts all trading activities immediately when active emergency triggers are detected."""

    def __init__(self, name: str = "emergency_stop", enabled: bool = True) -> None:
        super().__init__(name=name, enabled=enabled)

    async def evaluate(self, context: Dict[str, Any]) -> PolicyResult:
        """Evaluate emergency stop status."""
        if not self.enabled:
            return PolicyResult(
                policy_name=self.name,
                status=PolicyStatus.PASSED,
                message="EMERGENCY STOP: Policy disabled",
                passed=True,
            )

        triggers: List[str] = context.get("emergency_triggers", [])
        is_triggered: bool = context.get("is_emergency_stop", False) or len(triggers) > 0

        if is_triggered:
            trigger_list_str = ", ".join(triggers) if triggers else "manual_override"
            msg = f"EMERGENCY STOP: Active triggers: {trigger_list_str}"
            return PolicyResult(
                policy_name=self.name,
                status=PolicyStatus.REJECTED,
                message=msg,
                passed=False,
                details={"active_triggers": triggers},
            )

        return PolicyResult(
            policy_name=self.name,
            status=PolicyStatus.PASSED,
            message="EMERGENCY STOP: Normal operation",
            passed=True,
        )
