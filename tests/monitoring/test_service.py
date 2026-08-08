"""
Unit tests for the MonitoringService.
"""
import asyncio

import pytest

from backend.app.monitoring.config import MonitoringConfig
from backend.app.monitoring.service import MonitoringService


@pytest.fixture
def service() -> MonitoringService:
    """Create an isolated monitoring service."""
    return MonitoringService(MonitoringConfig(metrics_interval_seconds=1))


class TestSystemMetrics:
    """Test system metrics collection."""

    def test_system_metrics_present(self, service):
        """System metrics should include all required fields."""
        metrics = service._get_system_metrics()
        assert metrics.cpu is not None
        assert metrics.memory is not None
        assert metrics.latency is not None
        assert metrics.requests >= 0
        assert metrics.errors >= 0
        assert metrics.queue is not None
        assert metrics.redis is not None
        assert metrics.workers >= 0
        assert metrics.prediction_rate >= 0

    def test_cpu_percent_in_range(self, service):
        """CPU percent should be between 0 and 100."""
        metrics = service._get_system_metrics()
        assert 0.0 <= metrics.cpu.percent <= 100.0

    def test_memory_percent_in_range(self, service):
        """Memory percent should be between 0 and 100."""
        metrics = service._get_system_metrics()
        assert 0.0 <= metrics.memory.percent <= 100.0


class TestPredictionRate:
    """Test prediction rate tracking."""

    def test_record_prediction(self, service):
        """Recording a prediction should update the rate."""
        service.record_prediction("scam")
        service.record_prediction("safe")
        assert service._prediction_counts.get("scam") == 1
        assert service._prediction_counts.get("safe") == 1
        assert len(service._prediction_timestamps) == 2

    def test_record_prediction_with_duration(self, service):
        """Recording with duration should update latency samples."""
        service.record_prediction("scam", duration_ms=150.0)
        assert len(service._latency_samples) == 1
        assert service._latency_samples[0] == 150.0

    def test_compute_prediction_rate(self, service):
        """Prediction rate should be computed over the window."""
        service.record_prediction("scam")
        service.record_prediction("scam")
        rate = service._compute_prediction_rate()
        assert rate >= 0


class TestAttackEvents:
    """Test attack event recording and aggregation."""

    def test_record_attack(self, service):
        """Recording an attack should add it to the events deque."""
        service.record_attack(
            source_ip="1.2.3.4",
            label="scam",
            risk_score=0.95,
            source="phishing.com",
            country="US",
        )
        assert len(service._attack_events) == 1
        event = service._attack_events[0]
        assert event.source_ip == "1.2.3.4"
        assert event.country == "US"
        assert event.risk_score == 0.95

    def test_country_stats_aggregation(self, service):
        """Country stats should aggregate by country."""
        service.record_attack(country="US", source="a.com")
        service.record_attack(country="US", source="b.com")
        service.record_attack(country="IN", source="c.com")
        stats = service._get_country_stats()
        assert len(stats) == 2
        us = next(s for s in stats if s.country == "US")
        ind = next(s for s in stats if s.country == "IN")
        assert us.count == 2
        assert ind.count == 1
        assert us.percentage == 66.67

    def test_top_scam_sources(self, service):
        """Top scam sources should be sorted by count."""
        service.record_attack(source="phishing.com", risk_score=0.9)
        service.record_attack(source="phishing.com", risk_score=0.8)
        service.record_attack(source="scam.net", risk_score=0.7)
        sources = service._get_top_scam_sources()
        assert sources[0].source == "phishing.com"
        assert sources[0].count == 2
        assert sources[0].avg_risk == 0.85

    def test_dangerous_domains(self, service):
        """Dangerous domains should be aggregated by source."""
        service.record_attack(source="evil.com", risk_score=0.95)
        service.record_attack(source="evil.com", risk_score=0.85)
        domains = service._get_dangerous_domains()
        assert len(domains) == 1
        assert domains[0].domain == "evil.com"
        assert domains[0].detections == 2
        assert domains[0].risk_score == 0.9


class TestOverview:
    """Test overview generation."""

    @pytest.mark.asyncio
    async def test_get_overview(self, service):
        """Overview should include all sections."""
        service.record_prediction("scam")
        service.record_attack(source="evil.com", country="US", risk_score=0.9)
        overview = await service.get_overview()
        assert overview.system is not None
        assert overview.prediction_rate.count >= 0
        assert len(overview.attack_events) == 1
        assert overview.country_stats is not None
        assert overview.top_scam_sources is not None
        assert overview.dangerous_domains is not None

    @pytest.mark.asyncio
    async def test_health_check(self, service):
        """Health check should report healthy."""
        health = await service.health_check()
        assert health["status"] == "healthy"
        assert health["enabled"] is True
        assert health["websocket_enabled"] is True
