"""
Monitoring Module Schemas
===========================
Pydantic models for the Real-Time Monitoring Center.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


# =============================================================================
# System Metrics
# =============================================================================

class CpuMetric(BaseModel):
    """CPU usage metrics."""

    percent: float = Field(..., ge=0.0, le=100.0, description="CPU usage percentage")
    cores: int = Field(default=0, description="Number of CPU cores")
    load_avg: list[float] | None = Field(
        default=None, description="Load average (1, 5, 15 min)"
    )


class MemoryMetric(BaseModel):
    """Memory usage metrics."""

    total_bytes: int = Field(..., ge=0)
    used_bytes: int = Field(..., ge=0)
    percent: float = Field(..., ge=0.0, le=100.0)
    available_bytes: int = Field(..., ge=0)


class LatencyMetric(BaseModel):
    """Request latency metrics."""

    avg_ms: float = Field(..., ge=0.0)
    p95_ms: float = Field(..., ge=0.0)
    p99_ms: float = Field(..., ge=0.0)
    max_ms: float = Field(..., ge=0.0)


class QueueMetric(BaseModel):
    """Queue metrics."""

    queued: int = Field(default=0, ge=0)
    active: int = Field(default=0, ge=0)
    rejected: int = Field(default=0, ge=0)
    max_size: int = Field(default=0, ge=0)


class RedisMetric(BaseModel):
    """Redis cache metrics."""

    connected: bool = Field(default=False)
    backend: str = Field(default="memory")
    cache_size: int = Field(default=0, ge=0)
    hits: int = Field(default=0, ge=0)
    misses: int = Field(default=0, ge=0)
    hit_rate: float = Field(default=0.0, ge=0.0, le=100.0)


class SystemMetrics(BaseModel):
    """Aggregate system metrics snapshot."""

    timestamp: datetime = Field(default_factory=_utcnow)
    cpu: CpuMetric
    memory: MemoryMetric
    latency: LatencyMetric
    requests: int = Field(..., ge=0)
    errors: int = Field(..., ge=0)
    queue: QueueMetric
    redis: RedisMetric
    workers: int = Field(..., ge=0)
    prediction_rate: float = Field(..., ge=0.0, description="Predictions per second")


# =============================================================================
# Prediction Rate
# =============================================================================

class PredictionRate(BaseModel):
    """Prediction rate over an interval."""

    timestamp: datetime = Field(default_factory=_utcnow)
    period_seconds: int = Field(..., ge=1)
    count: int = Field(..., ge=0)
    rate_per_second: float = Field(..., ge=0.0)
    by_label: dict[str, int] = Field(default_factory=dict)


# =============================================================================
# Attack Mapping
# =============================================================================

class AttackEvent(BaseModel):
    """A detected attack event for the world map."""

    id: str = Field(..., description="Unique event ID")
    timestamp: datetime = Field(default_factory=_utcnow)
    source_ip: str | None = Field(default=None)
    latitude: float | None = Field(default=None)
    longitude: float | None = Field(default=None)
    country: str | None = Field(default=None)
    city: str | None = Field(default=None)
    label: str = Field(..., description="Prediction label (scam/suspicious/safe)")
    risk_score: float = Field(..., ge=0.0, le=1.0)
    source: str | None = Field(default=None)


class CountryStat(BaseModel):
    """Country-level attack statistics."""

    country: str
    country_code: str | None = Field(default=None)
    count: int = Field(..., ge=0)
    percentage: float = Field(..., ge=0.0, le=100.0)


class TopScamSource(BaseModel):
    """Top scam source statistics."""

    source: str
    count: int = Field(..., ge=0)
    percentage: float = Field(..., ge=0.0, le=100.0)
    avg_risk: float = Field(..., ge=0.0, le=1.0)


class DangerousDomain(BaseModel):
    """A frequently flagged domain."""

    domain: str
    detections: int = Field(..., ge=0)
    risk_score: float = Field(..., ge=0.0, le=1.0)
    first_seen: datetime | None = Field(default=None)
    last_seen: datetime | None = Field(default=None)


# =============================================================================
# Overview Response
# =============================================================================

class MonitoringOverview(BaseModel):
    """Complete monitoring overview payload."""

    system: SystemMetrics
    prediction_rate: PredictionRate
    attack_events: list[AttackEvent]
    country_stats: list[CountryStat]
    top_scam_sources: list[TopScamSource]
    dangerous_domains: list[DangerousDomain]
    generated_at: datetime = Field(default_factory=_utcnow)


# =============================================================================
# WebSocket Message
# =============================================================================

class WsMessage(BaseModel):
    """WebSocket streaming message envelope."""

    type: str = Field(..., description="Message type (metrics/attack/overview)")
    payload: dict[str, Any]
    timestamp: datetime = Field(default_factory=_utcnow)
