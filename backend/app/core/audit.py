"""
Enterprise Audit Logging
=========================
Structured audit trail for all security-relevant events.
Implements immutable audit logging for compliance.
"""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class AuditLogger:
    """
    Enterprise audit logger.

    Records all security-relevant events with:
    - Timestamp (UTC)
    - Actor (user who performed the action)
    - Action (what was done)
    - Resource (what was affected)
    - Result (success/failure)
    - IP address
    - Correlation ID
    - Additional context
    """

    def __init__(self, log_dir: Path | None = None):
        self.log_dir = log_dir or Path("logs/audit")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._session_id = str(uuid.uuid4())

    def _get_audit_file(self) -> Path:
        """Get the current audit log file (rotated daily)."""
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        return self.log_dir / f"audit-{date_str}.jsonl"

    def log(
        self,
        action: str,
        actor: str | None = None,
        resource: str | None = None,
        resource_id: str | None = None,
        result: str = "success",
        ip_address: str | None = None,
        correlation_id: str | None = None,
        details: dict[str, Any] | None = None,
        severity: str = "info",
    ) -> None:
        """
        Write an audit log entry.

        Args:
            action: The action performed (e.g., "user.login", "model.predict")
            actor: Who performed the action (user email or system)
            resource: What was affected (e.g., "user", "scan", "model")
            resource_id: Identifier of the resource
            result: "success" or "failure"
            ip_address: Source IP
            correlation_id: Request correlation ID
            details: Additional context
            severity: "info", "warning", "critical"
        """
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "session_id": self._session_id,
            "correlation_id": correlation_id or str(uuid.uuid4()),
            "action": action,
            "actor": actor or "anonymous",
            "resource": resource or "unknown",
            "resource_id": resource_id,
            "result": result,
            "ip_address": ip_address or "unknown",
            "severity": severity,
            "details": details or {},
        }

        # Write to audit log file (append-only)
        audit_file = self._get_audit_file()
        with open(audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def query(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        action: str | None = None,
        actor: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query audit logs with filters."""
        results = []

        # List audit files
        pattern = "audit-*.jsonl"
        files = sorted(self.log_dir.glob(pattern), reverse=True)

        for file in files:
            if start_date:
                date_str = file.stem.replace("audit-", "")
                if date_str < start_date:
                    continue
            if end_date:
                date_str = file.stem.replace("audit-", "")
                if date_str > end_date:
                    continue

            with open(file, encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if action and entry.get("action") != action:
                            continue
                        if actor and entry.get("actor") != actor:
                            continue
                        results.append(entry)
                        if len(results) >= limit:
                            return results
                    except json.JSONDecodeError:
                        continue

        return results

    def get_security_summary(self, days: int = 7) -> dict[str, Any]:
        """Get summary of security events for the given period."""
        from datetime import timedelta

        start = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
        logs = self.query(start_date=start)

        summary = {
            "total_events": len(logs),
            "by_severity": {},
            "by_action": {},
            "failed_actions": [],
            "unique_actors": set(),
        }

        for entry in logs:
            severity = entry.get("severity", "info")
            summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1

            action = entry.get("action", "unknown")
            summary["by_action"][action] = summary["by_action"].get(action, 0) + 1

            if entry.get("result") == "failure":
                summary["failed_actions"].append(entry)

            actor = entry.get("actor")
            if actor:
                summary["unique_actors"].add(actor)

        summary["unique_actors"] = list(summary["unique_actors"])
        summary["unique_actor_count"] = len(summary["unique_actors"])

        return summary


# Singleton instance
_audit_logger_instance: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    global _audit_logger_instance
    if _audit_logger_instance is None:
        _audit_logger_instance = AuditLogger()
    return _audit_logger_instance


# =============================================================================
# Audit middleware for FastAPI
# =============================================================================


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware that automatically audits all API requests.
    """

    def __init__(
        self,
        app: ASGIApp,
        exclude_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/docs", "/openapi.json"]
        self.audit_logger = get_audit_logger()

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip excluded paths
        if any(request.url.path.startswith(p) for p in self.exclude_paths):
            return await call_next(request)

        # Extract actor from auth header if present
        actor = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            # We can't decode here without circular imports,
            # the route handler will log the full audit
            pass

        correlation_id = request.headers.get(
            "X-Correlation-ID",
            request.headers.get("X-Request-ID", str(uuid.uuid4())),
        )

        # Process request
        response = await call_next(request)

        # Audit log
        self.audit_logger.log(
            action=f"api.{request.method.lower()}.{request.url.path.replace('/', '.')}",
            actor=actor or "anonymous",
            resource="api",
            resource_id=request.url.path,
            result="success" if response.status_code < 400 else "failure",
            ip_address=request.client.host if request.client else None,
            correlation_id=correlation_id,
            details={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "user_agent": request.headers.get("user-agent"),
            },
            severity="warning" if response.status_code >= 400 else "info",
        )

        return response
