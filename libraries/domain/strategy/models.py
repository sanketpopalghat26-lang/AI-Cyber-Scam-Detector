"""Strategy Domain Models."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional


class SignalType(str, Enum):
    """Signal action types."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    FLAT = "FLAT"


class OrderType(str, Enum):
    """Order type enumeration."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


@dataclass(frozen=True)
class Signal:
    """Trading signal produced by a strategy."""

    strategy_id: str
    symbol: str
    signal_type: SignalType
    price: Decimal
    timestamp: datetime
    strength: Decimal = Decimal("1.0")
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Position:
    """Represents a open or closed strategy position."""

    symbol: str
    quantity: Decimal
    entry_price: Decimal
    entry_time: datetime
    side: SignalType
    current_price: Decimal = Decimal("0")

    @property
    def unrealized_pnl(self) -> Decimal:
        """Calculate current unrealized PnL."""
        if self.side == SignalType.BUY:
            return (self.current_price - self.entry_price) * self.quantity
        elif self.side == SignalType.SELL:
            return (self.entry_price - self.current_price) * self.quantity
        return Decimal("0")


@dataclass(frozen=True)
class StrategyConfig:
    """Configuration parameters for a strategy instance."""

    strategy_id: str
    name: str
    symbols: list[str]
    parameters: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
