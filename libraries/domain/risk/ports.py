"""Risk Domain Ports (Interfaces)."""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Sequence

from libraries.domain.risk.models import PolicyEvaluation, PolicyResult, RiskMetrics, StressResult, StressScenario


class RiskPolicyPort(ABC):
    """Port interface for a risk policy."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique policy identifier name."""
        ...

    @abstractmethod
    async def evaluate(self, context: Dict[str, Any]) -> PolicyResult:
        """Evaluate risk policy asynchronously given execution context."""
        ...


class StressTestPort(ABC):
    """Port interface for running stress tests."""

    @abstractmethod
    async def run_scenario(
        self,
        portfolio_value: Decimal,
        positions: Dict[str, Decimal],
        scenario: StressScenario,
    ) -> StressResult:
        """Run a stress test scenario asynchronously."""
        ...


class RiskAnalyticsPort(ABC):
    """Port interface for risk analytics calculations."""

    @abstractmethod
    def calculate_metrics(self, returns: Sequence[Decimal], capital: Decimal) -> RiskMetrics:
        """Calculate aggregate risk metrics."""
        ...


class RiskEnginePort(ABC):
    """Port interface for evaluating risk engine policies."""

    @abstractmethod
    async def evaluate_policies(self, context: Dict[str, Any]) -> PolicyEvaluation:
        """Evaluate registered policies concurrently."""
        ...
