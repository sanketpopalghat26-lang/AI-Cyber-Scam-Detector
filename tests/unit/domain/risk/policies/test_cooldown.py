"""Unit tests for CooldownTimerPolicy."""

from datetime import datetime, timedelta, timezone
import pytest

from libraries.domain.risk.policies.cooldown import CooldownTimerPolicy
from libraries.domain.risk.types import PolicyStatus


@pytest.mark.asyncio
async def test_cooldown_inactive() -> None:
    policy = CooldownTimerPolicy()
    result = await policy.evaluate({"current_time": datetime.now(timezone.utc)})
    assert result.passed is True
    assert result.status == PolicyStatus.PASSED


@pytest.mark.asyncio
async def test_cooldown_active() -> None:
    now = datetime.now(timezone.utc)
    cooldown_until = now + timedelta(minutes=15)
    policy = CooldownTimerPolicy(cooldown_end=cooldown_until)

    result = await policy.evaluate({"current_time": now})
    assert result.passed is False
    assert result.status == PolicyStatus.REJECTED
    assert "cooldown until" in result.message.lower()
    assert result.details.get("cooldown_end") == cooldown_until.isoformat()


@pytest.mark.asyncio
async def test_cooldown_expired() -> None:
    now = datetime.now(timezone.utc)
    cooldown_past = now - timedelta(minutes=5)
    policy = CooldownTimerPolicy(cooldown_end=cooldown_past)

    result = await policy.evaluate({"current_time": now})
    assert result.passed is True
    assert result.status == PolicyStatus.PASSED


@pytest.mark.asyncio
async def test_cooldown_set_and_clear() -> None:
    now = datetime.now(timezone.utc)
    policy = CooldownTimerPolicy()

    policy.set_cooldown(now + timedelta(minutes=10))
    res1 = await policy.evaluate({"current_time": now})
    assert res1.passed is False

    policy.clear_cooldown()
    res2 = await policy.evaluate({"current_time": now})
    assert res2.passed is True
