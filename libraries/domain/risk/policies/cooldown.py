"""Cooldown Timer Risk Policy with strict Optional narrowing."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from libraries.domain.risk.models import PolicyResult
from libraries.domain.risk.policies.base import BaseRiskPolicy
from libraries.domain.risk.types import PolicyStatus


class CooldownTimerPolicy(BaseRiskPolicy):
    """Enforces a mandatory cooldown period after a loss or drawdown threshold breach."""

    def __init__(
        self,
        name: str = "cooldown_timer",
        enabled: bool = True,
        cooldown_end: Optional[datetime] = None,
    ) -> None:
        super().__init__(name=name, enabled=enabled)
        self._cooldown_end: Optional[datetime] = cooldown_end

    def set_cooldown(self, until: datetime) -> None:
        """Set cooldown expiration time."""
        self._cooldown_end = until

    def clear_cooldown(self) -> None:
        """Clear active cooldown."""
        self._cooldown_end = None

    async def evaluate(self, context: Dict[str, Any]) -> PolicyResult:
        """Evaluate whether current time is within active cooldown period."""
        if not self.enabled:
            return PolicyResult(
                policy_name=self.name,
                status=PolicyStatus.PASSED,
                message="Cooldown policy disabled",
                passed=True,
            )

        current_time: datetime = context.get("current_time", datetime.now(timezone.utc))

        # Explicit Optional narrowing for mypy safety without type ignore
        cooldown_end = self._cooldown_end
        if cooldown_end is not None and current_time < cooldown_end:
            cooldown_iso = cooldown_end.isoformat()
            return PolicyResult(
                policy_name=self.name,
                status=PolicyStatus.REJECTED,
                message=f"Trading in cooldown until {cooldown_iso}",
                passed=False,
                details={"cooldown_end": cooldown_iso},
            )

        return PolicyResult(
            policy_name=self.name,
            status=PolicyStatus.PASSED,
            message="No active cooldown",
            passed=True,
        )
