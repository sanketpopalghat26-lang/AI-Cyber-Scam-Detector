
"""Unit tests for Threat Intelligence database models."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine

from backend.app.threat_intelligence.models import (
    IOCStatus,
    IOCType,
    RiskLevel,
    ThreatAnalysis,
    ThreatCategory,
    ThreatFeed,
    ThreatFeedSource,
    ThreatIOC,
    ThreatRiskScore,
    ThreatTimelineEntry,
)


@pytest.fixture
def session():
    """Create an in-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    SQLModel.metadata.drop_all(engine)


class TestThreatIOC:
    """Test ThreatIOC model creation and attributes."""

    def test_create_ioc(self, session):
        """Test creating a basic IOC entry."""
        ioc = ThreatIOC(
            ioc_value="192.168.1.1",
            ioc_type=IOCType.IP,
            threat_category=ThreatCategory.MALICIOUS_IP,
            confidence=0.95,
            severity=0.8,
            risk_score=0.85,
            source=ThreatFeedSource.ABUSEIPDB,
            country_code="US",
            asn="AS15169",
            asn_org="Google LLC",
            isp="Google",
        )
        session.add(ioc)
        session.commit()
        session.refresh(ioc)

        assert ioc.id is not None
        assert ioc.ioc_value == "192.168.1.1"
        assert ioc.ioc_type == IOCType.IP
        assert ioc.threat_category == ThreatCategory.MALICIOUS_IP
        assert ioc.confidence == 0.95
        assert ioc.status == IOCStatus.ACTIVE
        assert ioc.first_seen is not None
        assert ioc.last_seen is not None

    def test_create_domain_ioc(self, session):
        """Test creating a domain IOC."""
        ioc = ThreatIOC(
            ioc_value="malicious-site.com",
            ioc_type=IOCType.DOMAIN,
            threat_category=ThreatCategory.MALICIOUS_DOMAIN,
            risk_score=0.75,
            tags="phishing,fake-login",
        )
        session.add(ioc)
        session.commit()
        session.refresh(ioc)

        assert ioc.ioc_type == IOCType.DOMAIN
        assert ioc.tags == "phishing,fake-login"

    def test_create_url_ioc(self, session):
        """Test creating a URL IOC."""
        ioc = ThreatIOC(
            ioc_value="https://phishing-site.com/login?token=abc",
            ioc_type=IOCType.URL,
            threat_category=ThreatCategory.PHISHING,
            source=ThreatFeedSource.OPENPHISH,
        )
        session.add(ioc)
        session.commit()
        session.refresh(ioc)

        assert ioc.ioc_type == IOCType.URL
        assert ioc.source == ThreatFeedSource.OPENPHISH

    def test_ioc_default_status(self, session):
        """Test IOC defaults to ACTIVE status."""
        ioc = ThreatIOC(
            ioc_value="test.com",
            ioc_type=IOCType.DOMAIN,
        )
        assert ioc.status == IOCStatus.ACTIVE

    def test_ioc_expired_status(self, session):
        """Test IOC with expiration."""
        ioc = ThreatIOC(
            ioc_value="old-threat.com",
            ioc_type=IOCType.DOMAIN,
            status=IOCStatus.EXPIRED,
            expires_at=datetime.now(UTC) - timedelta(days=30),
        )
        session.add(ioc)
        session.commit()
        session.refresh(ioc)

        assert ioc.status == IOCStatus.EXPIRED
        assert ioc.expires_at is not None
        # SQLite stores naive datetime - compare as naive
        now_naive = datetime.now(UTC).replace(tzinfo=None)
        expires_naive = ioc.expires_at.replace(tzinfo=None) if ioc.expires_at.tzinfo else ioc.expires_at
        assert expires_naive < now_naive

    def test_ioc_with_extra_data(self, session):
        """Test IOC with JSON extra data."""
        ioc = ThreatIOC(
            ioc_value="10.0.0.1",
            ioc_type=IOCType.IP,
            extra_data={"source_ip": "10.0.0.1", "port": 443, "protocol": "https"},
        )
        session.add(ioc)
        session.commit()
        session.refresh(ioc)

        assert ioc.extra_data is not None
        assert ioc.extra_data["port"] == 443


class TestThreatFeed:
    """Test ThreatFeed model."""

    def test_create_feed(self, session):
        """Test creating a threat feed entry."""
        feed = ThreatFeed(
            source=ThreatFeedSource.VIRUSTOTAL,
            name="VirusTotal",
            enabled=True,
            update_interval=3600,
        )
        session.add(feed)
        session.commit()
        session.refresh(feed)

        assert feed.id is not None
        assert feed.source == ThreatFeedSource.VIRUSTOTAL
        assert feed.status == "idle"

    def test_feed_unique_source(self, session):
        """Test that feed sources must be unique."""
        feed1 = ThreatFeed(
            source=ThreatFeedSource.ABUSEIPDB,
            name="AbuseIPDB",
        )
        session.add(feed1)
        session.commit()

        feed2 = ThreatFeed(
            source=ThreatFeedSource.ABUSEIPDB,
            name="AbuseIPDB Duplicate",
        )
        session.add(feed2)
        with pytest.raises(Exception):
            session.commit()


class TestThreatAnalysis:
    """Test ThreatAnalysis model."""

    def test_create_analysis(self, session):
        """Test creating an analysis record."""
        analysis = ThreatAnalysis(
            query_value="8.8.8.8",
            query_type=IOCType.IP,
            risk_score=0.2,
            risk_level=RiskLevel.LOW,
            is_malicious=False,
            confidence=0.95,
            sources_checked=3,
            provider_results={
                "virustotal": {"malicious": False, "confidence": 0.1}
            },
        )
        session.add(analysis)
        session.commit()
        session.refresh(analysis)

        assert analysis.id is not None
        assert not analysis.is_malicious
        assert analysis.risk_level == RiskLevel.LOW

    def test_malicious_analysis(self, session):
        """Test creating a malicious analysis record."""
        analysis = ThreatAnalysis(
            query_value="malicious-ip.com",
            query_type=IOCType.DOMAIN,
            risk_score=0.85,
            risk_level=RiskLevel.HIGH,
            threat_category=ThreatCategory.MALICIOUS_DOMAIN,
            is_malicious=True,
            confidence=0.92,
            sources_checked=5,
            positive_detections=4,
        )
        session.add(analysis)
        session.commit()
        session.refresh(analysis)

        assert analysis.is_malicious
        assert analysis.risk_level == RiskLevel.HIGH
        assert analysis.positive_detections == 4


class TestThreatTimelineEntry:
    """Test ThreatTimelineEntry model."""

    def test_create_timeline_entry(self, session):
        """Test creating a timeline entry."""
        entry = ThreatTimelineEntry(
            event_type="ioc_added",
            description="New malicious IP added: 10.0.0.1",
            severity=RiskLevel.HIGH,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)

        assert entry.id is not None
        assert entry.event_type == "ioc_added"
        assert entry.severity == RiskLevel.HIGH


class TestThreatRiskScore:
    """Test ThreatRiskScore model."""

    def test_create_risk_score(self, session):
        """Test creating a risk score record."""
        score = ThreatRiskScore(
            score_value=0.85,
            score_components={
                "virustotal": {"score": 0.9},
                "abuseipdb": {"score": 0.8},
            },
            risk_level=RiskLevel.HIGH,
        )
        session.add(score)
        session.commit()
        session.refresh(score)

        assert score.id is not None
        assert score.score_value == 0.85
        assert score.risk_level == RiskLevel.HIGH

