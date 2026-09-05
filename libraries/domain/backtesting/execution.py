"""Simulated Execution Handler for Backtesting."""

from decimal import Decimal

from libraries.domain.backtesting.ports import ExecutionPort
from libraries.domain.strategy.events import FillEvent, OrderEvent


class SimulatedExecutionHandler(ExecutionPort):
    """Simulates market order execution with customizable slippage and commission."""

    def __init__(self, commission_rate: Decimal = Decimal("0.0001"), slippage: Decimal = Decimal("0.0001")) -> None:
        self.commission_rate: Decimal = commission_rate
        self.slippage: Decimal = slippage

    async def execute_order(self, order: OrderEvent) -> FillEvent:
        """Execute order with simulated slippage and commission."""
        slippage_sign = Decimal("1") if order.side.value == "BUY" else Decimal("-1")
        fill_price = order.price + (self.slippage * slippage_sign)
        commission = fill_price * order.quantity * self.commission_rate

        return FillEvent(
            timestamp=order.timestamp,
            strategy_id=order.strategy_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            fill_price=fill_price,
            commission=commission,
        )
