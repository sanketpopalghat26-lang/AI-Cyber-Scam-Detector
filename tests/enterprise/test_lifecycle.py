"""
Lifecycle management tests.
Tests: startup, shutdown, graceful termination, signal handling.
"""
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.core.lifecycle import (
    GracefulShutdown,
    LifecycleManager,
    lifecycle,
    lifespan_handler,
)


class TestLifecycleManager:
    def test_add_startup_task(self):
        mgr = LifecycleManager()
        task = lambda: None
        mgr.add_startup_task(task, "test_task")
        assert len(mgr.startup_tasks) == 1

    def test_add_shutdown_task(self):
        mgr = LifecycleManager()
        task = lambda: None
        mgr.add_shutdown_task(task, "test_task")
        assert len(mgr.shutdown_tasks) == 1

    @pytest.mark.asyncio
    async def test_run_startup_success(self):
        mgr = LifecycleManager()
        called = []

        async def task():
            called.append(True)

        mgr.add_startup_task(task, "async_task")
        await mgr.run_startup()
        assert len(called) == 1

    @pytest.mark.asyncio
    async def test_run_startup_failure_continues(self):
        mgr = LifecycleManager()
        called = []

        async def failing_task():
            raise ValueError("Fail")

        async def success_task():
            called.append(True)

        mgr.add_startup_task(failing_task, "failing")
        mgr.add_startup_task(success_task, "success")

        # Should not raise in non-production
        await mgr.run_startup()
        assert len(called) == 1

    @pytest.mark.asyncio
    async def test_run_shutdown_reversed(self):
        mgr = LifecycleManager()
        order = []

        def task_a():
            order.append("a")

        def task_b():
            order.append("b")

        mgr.add_shutdown_task(task_a, "a")
        mgr.add_shutdown_task(task_b, "b")

        await mgr.run_shutdown()
        assert order == ["b", "a"]  # Reversed order

    @pytest.mark.asyncio
    async def test_shutdown_error_handling(self):
        mgr = LifecycleManager()

        async def failing():
            raise ValueError("Shutdown fail")

        async def success():
            pass

        mgr.add_shutdown_task(failing, "failing")
        mgr.add_shutdown_task(success, "success")

        # Should not raise
        await mgr.run_shutdown()


class TestGracefulShutdown:
    def test_initialization(self):
        from fastapi import FastAPI
        app = FastAPI()
        gs = GracefulShutdown(app, timeout_seconds=30)
        assert gs.timeout_seconds == 30
        assert gs._active_requests == 0

    @pytest.mark.asyncio
    async def test_shutdown_sets_flag(self):
        from fastapi import FastAPI
        app = FastAPI()
        app.state.shutting_down = False

        gs = GracefulShutdown(app, timeout_seconds=5)
        with patch.object(gs, '_active_requests', 0):
            with patch.object(lifecycle, 'run_shutdown', new_callable=AsyncMock) as mock_shutdown:
                await gs.shutdown()
                assert app.state.shutting_down is True
                mock_shutdown.assert_called_once()

    def test_active_requests_tracking(self):
        from fastapi import FastAPI
        app = FastAPI()
        gs = GracefulShutdown(app)
        assert gs._active_requests >= 0


class TestLifespanHandler:
    @pytest.mark.asyncio
    async def test_lifespan_context(self):
        from fastapi import FastAPI
        app = FastAPI()
        app.state.shutting_down = False

        async with lifespan_handler(app):
            assert app.state.shutting_down is False
            assert hasattr(app.state, 'startup_time')
            assert isinstance(app.state.startup_time, datetime)

        # After yield, shutdown tasks run
        assert app.state.shutting_down is True


class TestSecretsValidation:
    def test_secrets_validate_on_startup(self):
        from backend.app.core.secrets import validate_on_startup
        # Should not raise in testing environment
        validate_on_startup()

    def test_secrets_validator_all(self):
        from backend.app.core.secrets import SecretsValidator
        warnings = SecretsValidator.validate_all(environment="testing")
        assert isinstance(warnings, list)


class TestHealthCheckRegistration:
    @pytest.mark.asyncio
    async def test_health_checks_registered(self):
        from backend.app.core.lifecycle import _register_health_checks
        from backend.app.core.observability import _health_status

        await _register_health_checks()
        assert "database" in _health_status.checks
        assert "cache" in _health_status.checks

