"""Risk Domain Type Definitions."""

from enum import Enum


class RiskLevel(str, Enum):
    """Level of risk severity."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PolicyStatus(str, Enum):
    """Status of risk policy evaluation."""

    PASSED = "PASSED"
    REJECTED = "REJECTED"
    WARNING = "WARNING"
    INFORMATIONAL = "INFORMATIONAL"


class StressSeverity(str, Enum):
    """Stress test scenario severity level."""

    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    EXTREME = "EXTREME"
