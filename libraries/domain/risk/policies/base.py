"""Abstract Base Class for Risk Policies."""

from abc import ABC, abstractmethod
from typing import Any, Dict

from libraries.domain.risk.models import PolicyResult
from libraries.domain.risk.ports import RiskPolicyPort


class BaseRiskPolicy(RiskPolicyPort, ABC):
    """Base class for all risk policy rules."""

    def __init__(self, name: str, enabled: bool = True) -> None:
        self._name: str = name
        self.enabled: bool = enabled

    @property
    def name(self) -> str:
        """Policy identifier name."""
        return self._name

    @abstractmethod
    async def evaluate(self, context: Dict[str, Any]) -> PolicyResult:
        """Evaluate policy against given execution context."""
        ...
