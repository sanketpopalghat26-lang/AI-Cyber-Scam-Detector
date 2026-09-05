"""Strategy Ports (Interfaces)."""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional

from libraries.domain.market_data.models import Bar, Tick
from libraries.domain.strategy.events import MarketEvent, SignalEvent
from libraries.domain.strategy.models import Signal


class StrategyPort(ABC):
    """Port interface for strategy execution."""

    @abstractmethod
    async def on_tick(self, tick: Tick) -> Optional[Signal]:
        """Process incoming tick data."""
        ...

    @abstractmethod
    async def on_bar(self, bar: Bar) -> Optional[Signal]:
        """Process incoming bar data."""
        ...


class IndicatorPort(ABC):
    """Port interface for custom technical indicators."""

    @abstractmethod
    def calculate(self, values: list[Decimal]) -> Decimal:
        """Calculate indicator value from decimal values."""
        ...


class EventPublisherPort(ABC):
    """Port interface for publishing strategy events."""

    @abstractmethod
    async def publish_market_event(self, event: MarketEvent) -> None:
        """Publish market event."""
        ...

    @abstractmethod
    async def publish_signal_event(self, event: SignalEvent) -> None:
        """Publish signal event."""
        ...
