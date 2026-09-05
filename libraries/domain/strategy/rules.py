"""Strategy Rule evaluation classes."""

from abc import ABC, abstractmethod

from libraries.domain.market_data.models import Bar, Tick
from libraries.domain.strategy.context import StrategyContext


class EntryRule(ABC):
    """Rule determining position entry conditions."""

    @abstractmethod
    def evaluate(self, context: StrategyContext, tick: Tick | None, bar: Bar | None) -> bool:
        """Evaluate if entry conditions are satisfied."""
        ...


class ExitRule(ABC):
    """Rule determining position exit conditions."""

    @abstractmethod
    def evaluate(self, context: StrategyContext, tick: Tick | None, bar: Bar | None) -> bool:
        """Evaluate if exit conditions are satisfied."""
        ...


class FilterRule(ABC):
    """Rule filtering out invalid trading signals."""

    @abstractmethod
    def evaluate(self, context: StrategyContext, symbol: str) -> bool:
        """Evaluate if trade is allowed by filter."""
        ...
