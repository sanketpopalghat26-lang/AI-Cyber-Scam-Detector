"""
Real-Time Monitoring Center
============================
Enterprise-grade real-time monitoring module providing live system metrics,
prediction rate tracking, attack geolocation mapping, and WebSocket streaming.

This module follows Clean Architecture with domain-driven design (DDD)
patterns and is fully integrated with the enterprise observability,
resilience, caching, and security frameworks.

Feature Flag: ENABLE_MONITORING (default: true)
"""

from .config import MonitoringConfig
from .schemas import (
    SystemMetrics,
    CpuMetric,
    MemoryMetric,
    PredictionRate,
    AttackEvent,
    CountryStat,
    TopScamSource,
    DangerousDomain,
    MonitoringOverview,
)
from .service import MonitoringService
from .router import router

__all__ = [
    "MonitoringConfig",
    "SystemMetrics",
    "CpuMetric",
    "MemoryMetric",
    "PredictionRate",
    "AttackEvent",
    "CountryStat",
    "TopScamSource",
    "DangerousDomain",
    "MonitoringOverview",
    "MonitoringService",
    "router",
]
