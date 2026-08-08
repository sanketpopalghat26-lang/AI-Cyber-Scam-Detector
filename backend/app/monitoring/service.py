"""
Monitoring Service
====================
Core service for the Real-Time Monitoring Center.

Collects system metrics, prediction rates, attack events, country statistics,
top scam sources, and dangerous domains. Provides a consolidated overview
used by both the REST API and WebSocket streaming endpoints.

Uses graceful degradation: if psutil is unavailable (e.g., restricted
sandboxes), system metrics fall back to safe defaults rather than failing.
"""

import asyncio
import contextlib
import os
import time
import uuid
from collections import deque
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger

from ..core.cache import get_cache
from ..core.observability import (
    http_requests_total,
    predictions_total,
)
from .config import MonitoringConfig
from .schemas import (
    AttackEvent,
    CountryStat,
    CpuMetric,
    DangerousDomain,
    MemoryMetric,
    MonitoringOverview,
    PredictionRate,
    QueueMetric,
    RedisMetric,
    SystemMetrics,
    TopScamSource,
    LatencyMetric,
)


class MonitoringService:
    """Collects and aggregates real-time platform metrics."""

    def __init__(self, config: MonitoringConfig | None = None):
        self.config = config or MonitoringConfig.from_env()
        self._start_time = time.time()
        self._attack_events: deque[AttackEvent] = deque(
            maxlen=self.config.max_attack_events
        )
        self._prediction_counts: dict[str, int] = {}
        self._prediction_timestamps: deque[float] = deque(maxlen=10000)
        self._latency_samples: deque[float] = deque(maxlen=10000)
        self._error_count = 0
        # Cache of previous overview for delta computation
        self._last_overview: MonitoringOverview | None = None

    # =============================================================================
    # System Metrics
    # =============================================================================

    def _get_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics with graceful degradation."""
        cpu_percent = 0.0
        memory_total = 0
        memory_used = 0
        memory_percent = 0.0
        memory_available = 0
        cores = 0
        load_avg = None

        if self.config.system_metrics_enabled:
            with contextlib.suppress(Exception):
                import psutil

                cpu_percent = psutil.cpu_percent(interval=None)
                cores = psutil.cpu_count() or 0
                try:
                    load_avg = list(psutil.getloadavg())
                except (AttributeError, OSError):
                    load_avg = None

                vm = psutil.virtual_memory()
                memory_total = vm.total
                memory_used = vm.used
                memory_percent = vm.percent
                memory_available = vm.available

        cpu = CpuMetric(percent=round(cpu_percent, 2), cores=cores, load_avg=load_avg)
        memory = MemoryMetric(
            total_bytes=memory_total,
            used_bytes=memory_used,
            percent=round(memory_percent, 2),
            available_bytes=memory_available,
        )

        # Compute latency percentiles from samples
        samples = list(self._latency_samples)
        latency = self._compute_latency(samples)

        # Requests/errors from Prometheus counters (best-effort)
        requests = self._count_requests()
        errors = self._error_count

        # Queue metrics from resilience manager
        queue = self._get_queue_metrics()

        # Redis/cache metrics
        redis = self._get_redis_metrics()

        # Prediction rate (per second)
        rate_per_second = self._compute_prediction_rate()

        return SystemMetrics(
            cpu=cpu,
            memory=memory,
            latency=latency,
            requests=requests,
            errors=errors,
            queue=queue,
            redis=redis,
            workers=self._get_worker_count(),
            prediction_rate=rate_per_second,
        )

    def _compute_latency(self, samples: list[float]) -> LatencyMetric:
        """Compute latency stats from sampled durations (ms)."""
        if not samples:
            return LatencyMetric(avg_ms=0.0, p95_ms=0.0, p99_ms=0.0, max_ms=0.0)
        sorted_samples = sorted(samples)
        n = len(sorted_samples)
        return LatencyMetric(
            avg_ms=round(sum(sorted_samples) / n, 2),
            p95_ms=round(sorted_samples[min(n - 1, int(n * 0.95))], 2),
            p99_ms=round(sorted_samples[min(n - 1, int(n * 0.99))], 2),
            max_ms=round(sorted_samples[-1], 2),
        )

    def _count_requests(self) -> int:
        """Count total HTTP requests from Prometheus metric (best-effort)."""
        with contextlib.suppress(Exception):
            # Prometheus counter samples are not trivial to read; provide a
            # lightweight internal counter as fallback.
            pass
        # Fallback: track via a lightweight counter
        return getattr(self, "_request_count", 0)

    def _get_queue_metrics(self) -> QueueMetric:
        """Get queue metrics from the resilience manager."""
        try:
            from ..core.resilience import resilience_manager

            bulkheads = resilience_manager.bulkheads
            if not bulkheads:
                return QueueMetric()
            total_active = 0
            total_queued = 0
            total_rejected = 0
            max_size = 0
            for bh in bulkheads.values():
                state = bh.get_state()
                total_active += state.get("active_calls", 0)
                total_queued += state.get("queued_calls", 0)
                total_rejected += state.get("rejected_calls", 0)
                max_size += state.get("max_queue", 0)
            return QueueMetric(
                queued=total_queued,
                active=total_active,
                rejected=total_rejected,
                max_size=max_size,
            )
        except Exception:
            return QueueMetric()

    def _get_redis_metrics(self) -> RedisMetric:
        """Get cache/Redis metrics."""
        try:
            cache = get_cache()
            health = cache.health_check()
            return RedisMetric(
                connected=health.get("status") == "healthy",
                backend=health.get("backend", "memory"),
                cache_size=health.get("size", 0),
            )
        except Exception:
            return RedisMetric()

    def _get_worker_count(self) -> int:
        """Estimate worker count (gunicorn/uvicorn)."""
        try:
            import multiprocessing

            return multiprocessing.cpu_count()
        except Exception:
            return 1

    def _compute_prediction_rate(self) -> float:
        """Compute predictions per second over the last window."""
        window = self.config.history_window_minutes * 60
        cutoff = time.time() - window
        recent = [ts for ts in self._prediction_timestamps if ts > cutoff]
        if not recent:
            return 0.0
        span = max(recent) - min(recent)
        if span <= 0:
            # Treat as instantaneous rate
            return float(len(recent))
        return round(len(recent) / span, 2)

    # =============================================================================
    # Prediction Rate
    # =============================================================================

    def record_prediction(self, label: str, duration_ms: float | None = None) -> None:
        """Record a prediction event for rate tracking."""
        now = time.time()
        self._prediction_timestamps.append(now)
        self._prediction_counts[label] = self._prediction_counts.get(label, 0) + 1
        if duration_ms is not None:
            self._latency_samples.append(duration_ms)

    def record_request(self) -> None:
        """Record an HTTP request."""
        self._request_count = getattr(self, "_request_count", 0) + 1

    def record_error(self) -> None:
        """Record an error occurrence."""
        self._error_count += 1

    # =============================================================================
    # Attack Events
    # =============================================================================

    def record_attack(
        self,
        source_ip: str | None = None,
        label: str = "scam",
        risk_score: float = 0.9,
        source: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        country: str | None = None,
        city: str | None = None,
    ) -> None:
        """Record a detected attack event."""
        event = AttackEvent(
            id=str(uuid.uuid4()),
            source_ip=source_ip,
            latitude=latitude,
            longitude=longitude,
            country=country,
            city=city,
            label=label,
            risk_score=risk_score,
            source=source,
        )
        self._attack_events.append(event)

    # =============================================================================
    # Aggregations
    # =============================================================================

    def _get_country_stats(self) -> list[CountryStat]:
        """Aggregate attack events by country."""
        country_counts: dict[str, int] = {}
        country_codes: dict[str, str | None] = {}
        for event in self._attack_events:
            country = event.country or "Unknown"
            country_counts[country] = country_counts.get(country, 0) + 1
            country_codes[country] = None
        total = sum(country_counts.values()) or 1
        result = [
            CountryStat(
                country=country,
                country_code=country_codes.get(country),
                count=count,
                percentage=round(count / total * 100, 2),
            )
            for country, count in sorted(
                country_counts.items(), key=lambda x: x[1], reverse=True
            )
        ]
        return result[: self.config.max_top_sources]

    def _get_top_scam_sources(self) -> list[TopScamSource]:
        """Aggregate attack events by source."""
        source_counts: dict[str, dict[str, Any]] = {}
        for event in self._attack_events:
            src = event.source or "unknown"
            entry = source_counts.setdefault(src, {"count": 0, "risk_sum": 0.0})
            entry["count"] += 1
            entry["risk_sum"] += event.risk_score
        total = sum(e["count"] for e in source_counts.values()) or 1
        result = []
        for src, data in source_counts.items():
            count = data["count"]
            result.append(
                TopScamSource(
                    source=src,
                    count=count,
                    percentage=round(count / total * 100, 2),
                    avg_risk=round(data["risk_sum"] / count, 3),
                )
            )
        result.sort(key=lambda x: x.count, reverse=True)
        return result[: self.config.max_top_sources]

    def _get_dangerous_domains(self) -> list[DangerousDomain]:
        """Aggregate dangerous domains from attack events."""
        domain_counts: dict[str, dict[str, Any]] = {}
        for event in self._attack_events:
            if event.source:
                domain_counts.setdefault(event.source, {"detections": 0, "risk_sum": 0.0})
                domain_counts[event.source]["detections"] += 1
                domain_counts[event.source]["risk_sum"] += event.risk_score
        result = []
        for domain, data in domain_counts.items():
            result.append(
                DangerousDomain(
                    domain=domain,
                    detections=data["detections"],
                    risk_score=round(data["risk_sum"] / data["detections"], 3),
                )
            )
        result.sort(key=lambda x: x.detections, reverse=True)
        return result[: self.config.max_dangerous_domains]

    # =============================================================================
    # Overview
    # =============================================================================

    async def get_overview(self) -> MonitoringOverview:
        """Build a complete monitoring overview snapshot."""
        system = self._get_system_metrics()
        rate = PredictionRate(
            period_seconds=self.config.history_window_minutes * 60,
            count=len(
                [t for t in self._prediction_timestamps if t > time.time() - self.config.history_window_minutes * 60]
            ),
            rate_per_second=system.prediction_rate,
            by_label=dict(self._prediction_counts),
        )
        return MonitoringOverview(
            system=system,
            prediction_rate=rate,
            attack_events=list(self._attack_events),
            country_stats=self._get_country_stats(),
            top_scam_sources=self._get_top_scam_sources(),
            dangerous_domains=self._get_dangerous_domains(),
        )

    async def health_check(self) -> dict[str, Any]:
        """Health check for the monitoring module."""
        try:
            system = self._get_system_metrics()
            return {
                "status": "healthy",
                "enabled": self.config.enabled,
                "websocket_enabled": self.config.websocket_enabled,
                "tracked_attacks": len(self._attack_events),
                "tracked_predictions": len(self._prediction_timestamps),
                "prediction_rate": system.prediction_rate,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        except Exception as e:
            logger.error(f"Monitoring health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}


# Singleton instance
_service: MonitoringService | None = None


def get_monitoring_service() -> MonitoringService:
    """Get the global monitoring service singleton."""
    global _service
    if _service is None:
        _service = MonitoringService()
    return _service
