"""Strategy Context for managing internal runtime state, positions, and capital."""

from decimal import Decimal
from typing import Dict, Optional

from libraries.domain.strategy.models import Position


class StrategyContext:
    """Runtime execution context for a strategy."""

    def __init__(self, initial_capital: Decimal) -> None:
        self.initial_capital: Decimal = initial_capital
        self.cash: Decimal = initial_capital
        self.positions: Dict[str, Position] = {}

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get open position for symbol."""
        return self.positions.get(symbol)

    def set_position(self, symbol: str, position: Optional[Position]) -> None:
        """Update or clear open position for symbol."""
        if position is None:
            self.positions.pop(symbol, None)
        else:
            self.positions[symbol] = position

    @property
    def total_equity(self) -> Decimal:
        """Calculate total current account equity."""
        unrealized = sum(
            (pos.unrealized_pnl for pos in self.positions.values()),
            Decimal("0"),
        )
        return self.cash + unrealized
