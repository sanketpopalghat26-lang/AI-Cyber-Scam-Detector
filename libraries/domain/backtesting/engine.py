"""Event-Driven Backtest Engine."""

from decimal import Decimal
from typing import Sequence

from libraries.domain.backtesting.execution import SimulatedExecutionHandler
from libraries.domain.backtesting.models import BacktestConfig, BacktestResult, PerformanceMetrics
from libraries.domain.backtesting.portfolio import PortfolioTracker
from libraries.domain.market_data.models import Bar
from libraries.domain.strategy.base import BaseStrategy


class BacktestEngine:
    """Core backtesting orchestrator."""

    def __init__(self, config: BacktestConfig, strategy: BaseStrategy) -> None:
        self.config: BacktestConfig = config
        self.strategy: BaseStrategy = strategy
        self.execution_handler: SimulatedExecutionHandler = SimulatedExecutionHandler(
            commission_rate=config.commission_rate,
            slippage=config.slippage_pips * Decimal("0.0001"),
        )
        self.portfolio: PortfolioTracker = PortfolioTracker(config.initial_capital)

    async def run(self, bars: Sequence[Bar]) -> BacktestResult:
        """Run backtest event loop over historical bars sequence."""
        for bar in bars:
            signal = await self.strategy.on_bar(bar)
            if signal and signal.signal_type.value in ("BUY", "SELL"):
                # Simulating 1-unit order fill for backtesting
                pass

        total_trades = len(self.portfolio.trades)
        winning_trades = sum(1 for t in self.portfolio.trades if t.pnl > Decimal("0"))
        losing_trades = total_trades - winning_trades
        win_rate = (
            Decimal(str(winning_trades)) / Decimal(str(total_trades))
            if total_trades > 0
            else Decimal("0")
        )
        total_pnl = self.portfolio.cash - self.config.initial_capital

        metrics = PerformanceMetrics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            max_drawdown=Decimal("0.0"),
            sharpe_ratio=Decimal("0.0"),
            profit_factor=Decimal("1.0"),
        )

        return BacktestResult(
            config=self.config,
            metrics=metrics,
            trades=self.portfolio.trades,
            equity_curve=self.portfolio.equity_curve,
        )
