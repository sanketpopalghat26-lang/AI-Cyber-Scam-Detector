"""Abstract Base Class for Strategy implementations."""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional

from libraries.domain.market_data.models import Bar, Tick
from libraries.domain.strategy.context import StrategyContext
from libraries.domain.strategy.models import Signal, StrategyConfig
from libraries.domain.strategy.ports import StrategyPort


class BaseStrategy(StrategyPort, ABC):
    """Base class for trading strategies."""

    def __init__(self, config: StrategyConfig, initial_capital: Decimal) -> None:
        self.config: StrategyConfig = config
        self.context: StrategyContext = StrategyContext(initial_capital)

    @property
    def strategy_id(self) -> str:
        """Returns strategy identifier."""
        return self.config.strategy_id

    @abstractmethod
    async def on_tick(self, tick: Tick) -> Optional[Signal]:
        """Handle market tick."""
        ...

    @abstractmethod
    async def on_bar(self, bar: Bar) -> Optional[Signal]:
        """Handle market bar."""
        ...
