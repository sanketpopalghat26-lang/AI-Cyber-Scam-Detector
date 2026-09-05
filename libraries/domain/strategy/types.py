"""Strategy Domain Type Definitions."""

from decimal import Decimal
from typing import NewType

StrategyID = NewType("StrategyID", str)
Symbol = NewType("Symbol", str)
Price = NewType("Price", Decimal)
Quantity = NewType("Quantity", Decimal)
