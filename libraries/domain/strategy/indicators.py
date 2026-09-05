"""Technical Indicators implemented with high Decimal precision."""

from abc import ABC, abstractmethod
from collections import deque
from decimal import Decimal
from typing import Optional


class TechnicalIndicator(ABC):
    """Abstract base class for technical indicators."""

    @abstractmethod
    def update(self, price: Decimal) -> Optional[Decimal]:
        """Update indicator with new price data point and return current value if ready."""
        ...

    @property
    @abstractmethod
    def is_ready(self) -> bool:
        """Check whether indicator has sufficient data points to compute value."""
        ...


class SMA(TechnicalIndicator):
    """Simple Moving Average (SMA) using Decimal."""

    def __init__(self, period: int) -> None:
        if period <= 0:
            raise ValueError("Period must be greater than 0")
        self.period: int = period
        self.prices: deque[Decimal] = deque(maxlen=period)

    def update(self, price: Decimal) -> Optional[Decimal]:
        """Add price and compute simple moving average."""
        self.prices.append(price)
        if not self.is_ready:
            return None
        total = sum(self.prices, Decimal("0"))
        return total / Decimal(str(len(self.prices)))

    @property
    def is_ready(self) -> bool:
        """True if number of samples equals period."""
        return len(self.prices) == self.period
