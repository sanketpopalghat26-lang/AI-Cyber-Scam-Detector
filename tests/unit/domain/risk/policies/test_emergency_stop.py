"""Unit tests for EmergencyStopPolicy verifying trigger name presence in result message."""

import pytest
from libraries.domain.risk.policies.emergency_stop import EmergencyStopPolicy
from libraries.domain.risk.types import PolicyStatus


@pytest.mark.asyncio
async def test_emergency_stop_normal_operation() -> None:
    policy = EmergencyStopPolicy()
    result = await policy.evaluate({})
    assert result.passed is True
    assert result.status == PolicyStatus.PASSED
    assert "EMERGENCY STOP" in result.message


@pytest.mark.asyncio
async def test_emergency_stop_single_trigger() -> None:
    policy = EmergencyStopPolicy()
    context = {"emergency_triggers": ["broker_disconnect"]}
    result = await policy.evaluate(context)

    assert result.passed is False
    assert result.status == PolicyStatus.REJECTED
    assert "EMERGENCY STOP" in result.message
    assert "broker_disconnect" in result.message


@pytest.mark.asyncio
async def test_emergency_stop_multiple_triggers() -> None:
    policy = EmergencyStopPolicy()
    context = {"emergency_triggers": ["broker_disconnect", "drawdown_exceeded"]}
    result = await policy.evaluate(context)

    assert result.passed is False
    assert result.status == PolicyStatus.REJECTED
    assert "EMERGENCY STOP" in result.message
    assert "broker_disconnect" in result.message
    assert "drawdown_exceeded" in result.message


@pytest.mark.asyncio
async def test_emergency_stop_disabled() -> None:
    policy = EmergencyStopPolicy(enabled=False)
    context = {"emergency_triggers": ["broker_disconnect"]}
    result = await policy.evaluate(context)
    assert result.passed is True
