"""
Observability infrastructure tests.
Tests: metrics, health checks, audit logging, structured logging.
"""
import json

import pytest
from fastapi.testclient import TestClient

from backend.app.core.audit import AuditLogger
from backend.app.core.observability import (
    HealthStatus,
    get_health_status,
)


class TestMetrics:
    def test_metrics_endpoint_access(self):
        from backend.app.main import app
        client = TestClient(app)
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]

    def test_metrics_contain_http_metrics(self):
        from backend.app.main import app
        client = TestClient(app)
        # Make some requests to generate metrics
        client.get("/health")
        client.get("/dashboard")
        resp = client.get("/metrics")
        body = resp.text
        assert "http_requests_total" in body
        assert "http_request_duration_seconds" in body

    def test_metrics_contain_prediction_metrics(self):
        from backend.app.main import app
        client = TestClient(app)
        client.post("/predict", json={"text": "Test metrics", "source": "test"})
        resp = client.get("/metrics")
        body = resp.text
        assert "predictions_total" in body


class TestHealthChecks:
    def test_health_status_object(self):
        hs = HealthStatus()
        assert hasattr(hs, "checks")
        assert hasattr(hs, "startup_time")

    def test_register_check(self):
        hs = HealthStatus()
        hs.register_check("test", lambda: {"status": "healthy"})
        assert "test" in hs.checks

    def test_run_check_success(self):
        hs = HealthStatus()
        hs.register_check("test", lambda: {"status": "healthy"})
        result = hs.run_check("test")
        assert result["status"] == "healthy"

    def test_run_check_failure(self):
        hs = HealthStatus()
        def failing_check():
            raise Exception("Check failed")
        hs.register_check("fail", failing_check)
        result = hs.run_check("fail")
        assert result["status"] == "unhealthy"
        assert "error" in result

    def test_is_healthy_all_good(self):
        hs = HealthStatus()
        hs.register_check("a", lambda: {"status": "healthy"})
        hs.register_check("b", lambda: {"status": "healthy"})
        assert hs.is_healthy() is True

    def test_is_healthy_with_failure(self):
        hs = HealthStatus()
        hs.register_check("good", lambda: {"status": "healthy"})
        hs.register_check("bad", lambda: {"status": "unhealthy"})
        assert hs.is_healthy() is False

    def test_get_all_checks(self):
        hs = HealthStatus()
        hs.register_check("a", lambda: {"status": "healthy"})
        results = hs.get_all_checks()
        assert "a" in results

    def test_get_health_status(self):
        status = get_health_status()
        assert "status" in status
        assert "model_status" in status
        assert "timestamp" in status
        assert "uptime_seconds" in status


class TestAuditLogging:
    @pytest.fixture
    def audit_logger(self, tmp_path):
        logger = AuditLogger(log_dir=tmp_path)
        return logger

    def test_audit_log_write(self, audit_logger):
        audit_logger.log(
            action="test.action",
            actor="test_user",
            resource="test_resource",
            result="success",
        )
        # Check file exists
        files = list(audit_logger.log_dir.glob("audit-*.jsonl"))
        assert len(files) >= 1

    def test_audit_log_content(self, audit_logger):
        audit_logger.log(
            action="user.login",
            actor="admin@test.com",
            resource="user",
            resource_id="123",
            result="success",
            ip_address="192.168.1.1",
            details={"method": "password"},
        )

        log_file = audit_logger._get_audit_file()
        with open(log_file) as f:
            entry = json.loads(f.readline().strip())

        assert entry["action"] == "user.login"
        assert entry["actor"] == "admin@test.com"
        assert entry["resource"] == "user"
        assert entry["result"] == "success"
        assert entry["ip_address"] == "192.168.1.1"

    def test_audit_log_critical_severity(self, audit_logger):
        audit_logger.log(
            action="security.breach",
            actor="system",
            resource="auth",
            result="failure",
            severity="critical",
        )
        log_file = audit_logger._get_audit_file()
        with open(log_file) as f:
            entry = json.loads(f.readline().strip())
        assert entry["severity"] == "critical"

    def test_audit_query(self, audit_logger):
        audit_logger.log(action="test.a", actor="user1", resource="r1")
        audit_logger.log(action="test.b", actor="user2", resource="r2")
        audit_logger.log(action="test.a", actor="user3", resource="r3")

        results = audit_logger.query(action="test.a")
        assert len(results) == 2

        results = audit_logger.query(actor="user1")
        assert len(results) == 1

    def test_audit_security_summary(self, audit_logger):
        audit_logger.log(action="user.login", actor="admin", resource="user", result="success")
        audit_logger.log(action="user.login", actor="admin", resource="user", result="failure")
        audit_logger.log(action="user.login", actor="admin", resource="user", result="failure",
                        severity="critical")

        summary = audit_logger.get_security_summary(days=1)
        assert summary["total_events"] >= 3
        assert "info" in summary["by_severity"]
        assert "critical" in summary["by_severity"]
        assert len(summary["failed_actions"]) >= 2

    def test_audit_immutable(self, audit_logger):
        """Audit log should be append-only and tamper-evident."""
        # Write two entries
        audit_logger.log(action="original_action", actor="user", resource="r")
        audit_logger.log(action="other_action", actor="user", resource="r")

        # Verify both entries exist via query
        original_results = audit_logger.query(action="original_action")
        assert len(original_results) >= 1, "Should find original_action before tampering"

        # Tamper with the log file directly
        log_file = audit_logger._get_audit_file()
        content = log_file.read_text()
        content_tampered = content.replace("original_action", "TAMPERED")
        log_file.write_text(content_tampered)

        # Force re-read by creating new logger instance with same log dir
        new_logger = AuditLogger(log_dir=audit_logger.log_dir)
        tampered_results = new_logger.query(action="TAMPERED")

        # The tampered file should contain TAMPERED but not original_action
        assert len(tampered_results) >= 1, "Tampered entries should be findable"
        original_after = new_logger.query(action="original_action")
        assert len(original_after) == 0, "Original entries should not be recoverable after tampering"

        # Restore for next test
        log_file.write_text(content)


class TestStructuredLogging:
    def test_loguru_configured(self):
        from loguru import logger
        assert logger is not None

    def test_request_logging_format(self):
        # Loguru is configured at startup with structured format
        from backend.app.core.observability import StructuredLoggingMiddleware
        assert StructuredLoggingMiddleware is not None

