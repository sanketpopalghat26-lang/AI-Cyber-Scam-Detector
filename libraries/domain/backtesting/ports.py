"""Backtesting Domain Ports."""

from abc import ABC, abstractmethod

from libraries.domain.backtesting.models import BacktestResult, Trade
from libraries.domain.strategy.events import FillEvent, OrderEvent


class ExecutionPort(ABC):
    """Port interface for order execution handling in backtest."""

    @abstractmethod
    async def execute_order(self, order: OrderEvent) -> FillEvent:
        """Simulate order execution."""
        ...


class BacktestRepositoryPort(ABC):
    """Port interface for storing backtest results."""

    @abstractmethod
    async def save_result(self, result: BacktestResult) -> None:
        """Save backtest result."""
        ...

    @abstractmethod
    async def save_trades(self, trades: list[Trade]) -> None:
        """Save recorded backtest trades."""
        ...
