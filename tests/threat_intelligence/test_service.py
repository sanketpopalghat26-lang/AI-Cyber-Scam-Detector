"""Unit tests for the Threat Intelligence service layer."""

import os

import pytest

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("ENABLE_THREAT_INTEL", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-32-chars-minimum!!")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

from backend.app.threat_intelligence.config import ThreatIntelConfig
from backend.app.threat_intelligence.models import (
    IOCType,
    RiskLevel,
)
from backend.app.threat_intelligence.providers import (
    ProviderRegistry,
    _auto_detect_type,
    _extract_domain,
)
from backend.app.threat_intelligence.service import ThreatIntelligenceService


@pytest.fixture
def config():
    """Create test configuration."""
    return ThreatIntelConfig(
        enabled=True,
        ioc_cache_ttl=60,
    )


@pytest.fixture
def service(config):
    """Create threat intelligence service for testing."""
    return ThreatIntelligenceService(config)


class TestAutoDetectType:
    """Test IOC type auto-detection."""

    def test_detect_ipv4(self):
        assert _auto_detect_type("192.168.1.1") == IOCType.IP

    def test_detect_ipv6(self):
        assert _auto_detect_type("::1") == IOCType.IP
        assert _auto_detect_type("2001:db8::1") == IOCType.IP

    def test_detect_domain(self):
        assert _auto_detect_type("example.com") == IOCType.DOMAIN
        assert _auto_detect_type("sub.domain.co.uk") == IOCType.DOMAIN

    def test_detect_url(self):
        assert _auto_detect_type("https://example.com/login") == IOCType.URL
        assert _auto_detect_type("http://phishing.com") == IOCType.URL

    def test_detect_md5(self):
        assert _auto_detect_type("d41d8cd98f00b204e9800998ecf8427e") == IOCType.HASH_MD5

    def test_detect_sha1(self):
        hash_val = "a9993e364706816aba3e25717850c26c9cd0d89d"
        assert _auto_detect_type(hash_val) == IOCType.HASH_SHA1

    def test_detect_sha256(self):
        hash_val = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert _auto_detect_type(hash_val) == IOCType.HASH_SHA256

    def test_detect_email(self):
        assert _auto_detect_type("user@example.com") == IOCType.EMAIL

    def test_detect_unknown_defaults_to_url(self):
        assert _auto_detect_type("some-random-string") == IOCType.URL


class TestExtractDomain:
    """Test domain extraction from URLs."""

    def test_extract_from_url(self):
        assert _extract_domain("https://www.example.com/page") == "www.example.com"
        assert _extract_domain("http://example.com") == "example.com"

    def test_extract_from_domain(self):
        assert _extract_domain("example.com") == "example.com"

    def test_extract_with_port(self):
        assert _extract_domain("https://example.com:8080/path") == "example.com:8080"


class TestConfig:
    """Test ThreatIntelConfig."""

    def test_default_config(self):
        config = ThreatIntelConfig()
        assert config.enabled is True
        assert config.ioc_cache_ttl == 300
        assert config.risk_threshold_high == 0.7
        assert config.risk_threshold_medium == 0.4

    def test_providers_empty_when_no_keys(self):
        config = ThreatIntelConfig(
            virustotal_api_key=None,
            abuseipdb_api_key=None,
        )
        providers = config.get_enabled_providers()
        # Should still have non-API providers
        assert "openphish" in providers
        assert "dns" in providers
        assert "whois" in providers
        assert "geoip" in providers
        assert "virustotal" not in providers

    def test_providers_with_keys(self):
        config = ThreatIntelConfig(
            virustotal_api_key="test-key",
            abuseipdb_api_key="test-key",
        )
        providers = config.get_enabled_providers()
        assert "virustotal" in providers
        assert "abuseipdb" in providers

    def test_is_fully_configured(self):
        config = ThreatIntelConfig()
        assert config.is_fully_configured() is False

        config = ThreatIntelConfig(virustotal_api_key="key")
        assert config.is_fully_configured() is True


class TestScoreCalculation:
    """Test risk score calculation."""

    def test_calculate_risk_score(self, service):
        provider_results = [
            {"provider": "virustotal", "malicious": True, "confidence": 0.9},
            {"provider": "abuseipdb", "malicious": True, "confidence": 0.8},
            {"provider": "openphish", "malicious": False, "confidence": 0.0},
            {"provider": "phishtank", "malicious": True, "confidence": 0.7},
        ]
        score = service._calculate_risk_score(provider_results)
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be high because 3/4 malicious

    def test_calculate_risk_score_no_malicious(self, service):
        provider_results = [
            {"provider": "virustotal", "malicious": False, "confidence": 0.0},
            {"provider": "openphish", "malicious": False, "confidence": 0.0},
        ]
        score = service._calculate_risk_score(provider_results)
        assert score == 0.0

    def test_score_to_risk_level(self, service):
        assert service._score_to_risk_level(0.9) == RiskLevel.CRITICAL
        assert service._score_to_risk_level(0.7) == RiskLevel.HIGH
        assert service._score_to_risk_level(0.5) == RiskLevel.MEDIUM
        assert service._score_to_risk_level(0.2) == RiskLevel.LOW
        assert service._score_to_risk_level(0.05) == RiskLevel.INFO


class TestBuildExplanation:
    """Test explanation building."""

    def test_explanation_critical(self, service):
        explanation = service._build_explanation(
            "evil.com", IOCType.DOMAIN, 0.9, 4, 5
        )
        assert "Critical" in explanation
        assert "evil.com" in explanation

    def test_explanation_safe(self, service):
        explanation = service._build_explanation(
            "google.com", IOCType.DOMAIN, 0.0, 0, 5
        )
        assert "No significant threat" in explanation
        assert "google.com" in explanation


class TestProviderRegistry:
    """Test the provider registry."""

    def test_registry_initialization(self, config):
        registry = ProviderRegistry(config)
        providers = registry.get_all_providers()
        assert len(providers) > 0
        assert "virustotal" in providers
        assert "abuseipdb" in providers
        assert "openphish" in providers

    def test_get_provider(self, config):
        registry = ProviderRegistry(config)
        provider = registry.get_provider("virustotal")
        assert provider is not None
        assert provider.name == "virustotal"

    def test_get_nonexistent_provider(self, config):
        registry = ProviderRegistry(config)
        provider = registry.get_provider("nonexistent")
        assert provider is None

