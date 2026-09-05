"""Strategy Domain Event Definitions."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from libraries.domain.market_data.models import Bar, Tick
from libraries.domain.strategy.models import OrderType, SignalType


@dataclass(frozen=True)
class MarketEvent:
    """Event triggered by new market data arrival."""

    timestamp: datetime
    tick: Tick | None = None
    bar: Bar | None = None


@dataclass(frozen=True)
class SignalEvent:
    """Event representing a strategy signal generated."""

    timestamp: datetime
    strategy_id: str
    symbol: str
    signal_type: SignalType
    price: Decimal
    quantity: Decimal


@dataclass(frozen=True)
class OrderEvent:
    """Event representing an order submitted to broker/execution."""

    timestamp: datetime
    strategy_id: str
    symbol: str
    order_type: OrderType
    side: SignalType
    quantity: Decimal
    price: Decimal


@dataclass(frozen=True)
class FillEvent:
    """Event representing an executed order fill."""

    timestamp: datetime
    strategy_id: str
    symbol: str
    side: SignalType
    quantity: Decimal
    fill_price: Decimal
    commission: Decimal
