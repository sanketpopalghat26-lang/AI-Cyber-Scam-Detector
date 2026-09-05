"""Market Data Domain Models using Decimal for high financial precision."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class CurrencyPair:
    """Represents a Forex currency pair (e.g. EUR/USD)."""

    base_currency: str
    quote_currency: str

    @property
    def symbol(self) -> str:
        """Returns standard symbol notation (e.g. EURUSD)."""
        return f"{self.base_currency}{self.quote_currency}"


@dataclass(frozen=True)
class Instrument:
    """Represents a financial instrument."""

    symbol: str
    name: str
    asset_class: str
    pip_size: Decimal = Decimal("0.0001")
    lot_size: Decimal = Decimal("100000")


@dataclass(frozen=True)
class Tick:
    """Represents a single market price tick."""

    symbol: str
    bid: Decimal
    ask: Decimal
    timestamp: datetime
    volume: Decimal = Decimal("0")

    @property
    def mid(self) -> Decimal:
        """Calculates mid price."""
        return (self.bid + self.ask) / Decimal("2")

    @property
    def spread(self) -> Decimal:
        """Calculates bid-ask spread."""
        return self.ask - self.bid


@dataclass(frozen=True)
class Quote:
    """Represents a market quote."""

    symbol: str
    bid: Decimal
    ask: Decimal
    timestamp: datetime
    bid_volume: Optional[Decimal] = None
    ask_volume: Optional[Decimal] = None


@dataclass(frozen=True)
class Bar:
    """Represents an OHLCV candlestick bar."""

    symbol: str
    timeframe: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
