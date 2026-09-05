"""Portfolio Tracker for Backtesting."""

from decimal import Decimal

from libraries.domain.backtesting.models import Trade
from libraries.domain.strategy.events import FillEvent


class PortfolioTracker:
    """Tracks account balance, open positions, equity curve, and closed trades."""

    def __init__(self, initial_capital: Decimal) -> None:
        self.initial_capital: Decimal = initial_capital
        self.cash: Decimal = initial_capital
        self.equity_curve: list[Decimal] = [initial_capital]
        self.trades: list[Trade] = []

    def process_fill(self, fill: FillEvent) -> None:
        """Process fill event and adjust cash and records."""
        cost = fill.fill_price * fill.quantity + fill.commission
        if fill.side.value == "BUY":
            self.cash -= cost
        else:
            self.cash += (fill.fill_price * fill.quantity) - fill.commission

        self.equity_curve.append(self.cash)
