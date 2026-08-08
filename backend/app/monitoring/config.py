"""
Monitoring Module Configuration
=================================
"""

import os
from dataclasses import dataclass, field


@dataclass
class MonitoringConfig:
    """Configuration for the Real-Time Monitoring Center."""

    enabled: bool = os.getenv("ENABLE_MONITORING", "true").lower() == "true"
    websocket_enabled: bool = os.getenv(
        "MONITORING_WEBSOCKET_ENABLED", "true"
    ).lower() == "true"
    metrics_interval_seconds: int = int(
        os.getenv("MONITORING_METRICS_INTERVAL", "5")
    )
    history_window_minutes: int = int(
        os.getenv("MONITORING_HISTORY_WINDOW", "60")
    )
    max_attack_events: int = int(os.getenv("MONITORING_MAX_ATTACKS", "1000"))
    max_top_sources: int = int(os.getenv("MONITORING_MAX_SOURCES", "10"))
    max_dangerous_domains: int = int(
        os.getenv("MONITORING_MAX_DOMAINS", "10")
    )
    cache_ttl: int = int(os.getenv("MONITORING_CACHE_TTL", "10"))
    country_lookup_enabled: bool = os.getenv(
        "MONITORING_COUNTRY_LOOKUP", "false"
    ).lower() == "true"
    # Graceful fallback when psutil is unavailable
    system_metrics_enabled: bool = os.getenv(
        "MONITORING_SYSTEM_METRICS", "true"
    ).lower() == "true"

    @classmethod
    def from_env(cls) -> "MonitoringConfig":
        return cls()
