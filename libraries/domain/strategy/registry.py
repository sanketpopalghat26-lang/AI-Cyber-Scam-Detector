"""Strategy Registry for managing registered strategy classes."""

from typing import Dict, Type

from libraries.domain.strategy.base import BaseStrategy
from libraries.domain.strategy.exceptions import StrategyError


class StrategyRegistry:
    """Registry for discovering and instantiating strategies dynamically."""

    _strategies: Dict[str, Type[BaseStrategy]] = {}

    @classmethod
    def register(cls, name: str, strategy_cls: Type[BaseStrategy]) -> None:
        """Register a strategy class under a unique name."""
        cls._strategies[name] = strategy_cls

    @classmethod
    def get(cls, name: str) -> Type[BaseStrategy]:
        """Retrieve strategy class by registered name."""
        if name not in cls._strategies:
            raise StrategyError(f"Strategy '{name}' not found in registry")
        return cls._strategies[name]

    @classmethod
    def list_all(cls) -> list[str]:
        """List all registered strategy names."""
        return list(cls._strategies.keys())
