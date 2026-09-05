"""Risk Domain Data Models using Decimal for high financial precision."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from libraries.domain.risk.types import PolicyStatus, RiskLevel, StressSeverity


@dataclass(frozen=True)
class RiskMetrics:
    """Calculated risk metrics for a portfolio or account."""

    var_95: Decimal
    var_99: Decimal
    cvar_95: Decimal
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    calmar_ratio: Decimal
    max_drawdown: Decimal
    current_drawdown: Decimal
    gross_exposure: Decimal
    net_exposure: Decimal
    leverage: Decimal
    risk_level: RiskLevel = RiskLevel.LOW


@dataclass(frozen=True)
class RiskLimit:
    """Configured risk limit constraint."""

    limit_id: str
    name: str
    max_value: Decimal
    current_value: Decimal
    is_breached: bool = False


@dataclass(frozen=True)
class PositionRisk:
    """Risk breakdown for a single position."""

    symbol: str
    exposure: Decimal
    unrealized_pnl: Decimal
    weight: Decimal
    var_contribution: Decimal


@dataclass(frozen=True)
class StressScenario:
    """Hypothetical or historical stress scenario."""

    scenario_id: str
    name: str
    description: str
    severity: StressSeverity
    shocks: Dict[str, Decimal]


@dataclass(frozen=True)
class StressResult:
    """Outcome of running a stress scenario."""

    scenario_id: str
    scenario_name: str
    estimated_loss: Decimal
    loss_percentage: Decimal
    capital_remaining: Decimal
    is_acceptable: bool


@dataclass(frozen=True)
class PolicyResult:
    """Result of evaluating a single risk policy."""

    policy_name: str
    status: PolicyStatus
    message: str
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)
    position_scale_factor: Optional[Decimal] = None


@dataclass(frozen=True)
class PolicyEvaluation:
    """Aggregated evaluation across all policies."""

    timestamp: datetime
    overall_passed: bool
    results: List[PolicyResult]
    recommended_scale: Decimal = Decimal("1.0")
