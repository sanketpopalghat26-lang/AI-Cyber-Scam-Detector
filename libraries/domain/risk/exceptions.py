"""Risk Domain Exceptions."""


class RiskError(Exception):
    """Base exception for all risk domain errors."""

    pass


class PolicyViolationError(RiskError):
    """Raised when a blocking risk policy is violated."""

    pass


class StressTestError(RiskError):
    """Raised when a stress test execution fails."""

    pass
