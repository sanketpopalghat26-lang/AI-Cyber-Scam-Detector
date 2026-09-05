"""Unit tests for ExposureLimitPolicy."""

from decimal import Decimal
import pytest

from libraries.domain.risk.policies.exposure_limit import ExposureLimitPolicy
from libraries.domain.risk.types import PolicyStatus


@pytest.mark.asyncio
async def test_exposure_limit_pass() -> None:
    policy = ExposureLimitPolicy(max_gross_exposure=Decimal("2.0"))
    result = await policy.evaluate({"gross_exposure": Decimal("1.5")})
    assert result.passed is True
    assert result.status == PolicyStatus.PASSED


@pytest.mark.asyncio
async def test_exposure_limit_breached() -> None:
    policy = ExposureLimitPolicy(max_gross_exposure=Decimal("2.0"))
    result = await policy.evaluate({"gross_exposure": Decimal("2.5")})
    assert result.passed is False
    assert result.status == PolicyStatus.REJECTED
