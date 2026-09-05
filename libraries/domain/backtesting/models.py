"""Backtesting Models with Decimal precision."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Sequence

from libraries.domain.strategy.models import SignalType


@dataclass(frozen=True)
class Trade:
    """Completed trade record."""

    trade_id: str
    symbol: str
    side: SignalType
    quantity: Decimal
    entry_price: Decimal
    exit_price: Decimal
    entry_time: datetime
    exit_time: datetime
    pnl: Decimal
    commission: Decimal


@dataclass(frozen=True)
class PerformanceMetrics:
    """Summary metrics of a backtest run."""

    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    total_pnl: Decimal
    max_drawdown: Decimal
    sharpe_ratio: Decimal
    profit_factor: Decimal


@dataclass(frozen=True)
class BacktestConfig:
    """Backtesting execution configuration."""

    strategy_id: str
    symbols: list[str]
    start_date: datetime
    end_date: datetime
    initial_capital: Decimal = Decimal("100000.0")
    commission_rate: Decimal = Decimal("0.0001")
    slippage_pips: Decimal = Decimal("1.0")


@dataclass(frozen=True)
class BacktestResult:
    """Complete result of a backtesting run."""

    config: BacktestConfig
    metrics: PerformanceMetrics
    trades: Sequence[Trade] = field(default_factory=list)
    equity_curve: Sequence[Decimal] = field(default_factory=list)
