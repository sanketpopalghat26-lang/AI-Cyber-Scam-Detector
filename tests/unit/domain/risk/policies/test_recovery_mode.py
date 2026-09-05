"""Unit tests for RecoveryModePolicy evaluating position-sizing and strict blocking semantics."""

from decimal import Decimal
import pytest

from libraries.domain.risk.policies.recovery_mode import RecoveryModePolicy
from libraries.domain.risk.types import PolicyStatus


@pytest.mark.asyncio
async def test_recovery_mode_normal() -> None:
    policy = RecoveryModePolicy()
    result = await policy.evaluate({"in_recovery_mode": False, "current_drawdown": Decimal("0.05")})

    assert result.passed is True
    assert result.status == PolicyStatus.PASSED
    assert result.position_scale_factor == Decimal("1.0")


@pytest.mark.asyncio
async def test_recovery_mode_position_scaling() -> None:
    policy = RecoveryModePolicy(recovery_scale_factor=Decimal("0.5"))
    result = await policy.evaluate({"in_recovery_mode": True, "current_drawdown": Decimal("0.08")})

    assert result.passed is True
    assert result.status == PolicyStatus.INFORMATIONAL
    assert result.position_scale_factor == Decimal("0.5")


@pytest.mark.asyncio
async def test_recovery_mode_strict_blocking_gate() -> None:
    """Tests RecoveryModePolicy when configured as a contractual blocking risk gate."""
    policy = RecoveryModePolicy(is_blocking_gate=True, max_recovery_drawdown=Decimal("0.10"))
    result = await policy.evaluate({"in_recovery_mode": True, "current_drawdown": Decimal("0.12")})

    assert result.passed is False
    assert result.status == PolicyStatus.REJECTED
    assert result.position_scale_factor == Decimal("0.0")


@pytest.mark.asyncio
async def test_everything_goes_wrong_strict_blocking() -> None:
    """Test scenario where strict blocking is enforced during extreme recovery breach."""
    policy = RecoveryModePolicy()
    context = {"in_recovery_mode": True, "current_drawdown": Decimal("0.25"), "strict_blocking": True}
    result = await policy.evaluate(context)

    assert result.passed is False
    assert result.status == PolicyStatus.REJECTED
