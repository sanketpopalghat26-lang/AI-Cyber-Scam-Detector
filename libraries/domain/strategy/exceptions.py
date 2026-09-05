"""Strategy Domain Exceptions."""


class StrategyError(Exception):
    """Base exception for all strategy errors."""

    pass


class StrategyConfigError(StrategyError):
    """Raised when strategy configuration is invalid."""

    pass


class ExecutionError(StrategyError):
    """Raised when strategy execution fails."""

    pass
