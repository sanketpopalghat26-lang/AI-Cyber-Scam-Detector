"""Market Data Domain Ports (Interfaces)."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import AsyncGenerator, Sequence

from libraries.domain.market_data.models import Bar, Tick


class MarketDataFeedPort(ABC):
    """Port interface for streaming market data feeds."""

    @abstractmethod
    async def subscribe_ticks(self, symbol: str) -> AsyncGenerator[Tick, None]:
        """Subscribe to real-time tick data for a given symbol."""
        ...

    @abstractmethod
    async def subscribe_bars(self, symbol: str, timeframe: str) -> AsyncGenerator[Bar, None]:
        """Subscribe to real-time bar data for a given symbol and timeframe."""
        ...


class MarketDataRepositoryPort(ABC):
    """Port interface for market data storage and historical retrieval."""

    @abstractmethod
    async def get_historical_bars(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Sequence[Bar]:
        """Retrieve historical bar sequence."""
        ...

    @abstractmethod
    async def save_bars(self, bars: Sequence[Bar]) -> None:
        """Save a batch of bar objects."""
        ...
