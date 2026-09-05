"""Unit tests for DrawdownLimitPolicy."""

from decimal import Decimal
import pytest

from libraries.domain.risk.policies.drawdown_limit import DrawdownLimitPolicy
from libraries.domain.risk.types import PolicyStatus


@pytest.mark.asyncio
async def test_drawdown_limit_pass() -> None:
    policy = DrawdownLimitPolicy(max_drawdown=Decimal("0.10"))
    result = await policy.evaluate({"current_drawdown": Decimal("0.05")})
    assert result.passed is True
    assert result.status == PolicyStatus.PASSED


@pytest.mark.asyncio
async def test_drawdown_limit_breach() -> None:
    policy = DrawdownLimitPolicy(max_drawdown=Decimal("0.10"))
    result = await policy.evaluate({"current_drawdown": Decimal("0.15")})
    assert result.passed is False
    assert result.status == PolicyStatus.REJECTED
