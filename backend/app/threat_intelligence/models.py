"""
Threat Intelligence Database Models
=====================================
SQLModel ORM models for IOC database, threat feeds, analysis records,
threat categories, timeline entries, and risk scores.

Follows DDD (Domain-Driven Design) with rich domain models.
All models include indexes, constraints, and relationships.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from sqlmodel import JSON, Field, Relationship, SQLModel, Text


def _utcnow() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


# =============================================================================
# Enums
# =============================================================================


class IOCType(str, Enum):
    """Types of Indicators of Compromise."""

    IP = "ip"
    DOMAIN = "domain"
    URL = "url"
    HASH_MD5 = "hash_md5"
    HASH_SHA1 = "hash_sha1"
    HASH_SHA256 = "hash_sha256"
    EMAIL = "email"
    PHONE = "phone"
    USERNAME = "username"
    ASN = "asn"
    SSL_FINGERPRINT = "ssl_fingerprint"


class ThreatCategory(str, Enum):
    """Categories of threats for classification."""

    MALWARE = "malware"
    PHISHING = "phishing"
    SCAM = "scam"
    SPAM = "spam"
    MALICIOUS_IP = "malicious_ip"
    MALICIOUS_DOMAIN = "malicious_domain"
    MALICIOUS_URL = "malicious_url"
    C2_SERVER = "c2_server"
    BOTNET = "botnet"
    RANSOMWARE = "ransomware"
    DDoS = "ddos"
    FRAUD = "fraud"
    SOCIAL_ENGINEERING = "social_engineering"
    BRUTE_FORCE = "brute_force"
    UNKNOWN = "unknown"


class ThreatFeedSource(str, Enum):
    """Sources of threat intelligence feeds."""

    VIRUSTOTAL = "virustotal"
    ABUSEIPDB = "abuseipdb"
    OPENPHISH = "openphish"
    PHISHTANK = "phishtank"
    ALIENVAULT_OTX = "alienvault_otx"
    DNS_ANALYSIS = "dns_analysis"
    WHOIS_LOOKUP = "whois_lookup"
    GEOIP_ANALYSIS = "geoip_analysis"
    ASN_LOOKUP = "asn_lookup"
    MANUAL = "manual"
    INTERNAL_ANALYSIS = "internal_analysis"


class RiskLevel(str, Enum):
    """Risk levels for threat assessment."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    UNKNOWN = "unknown"


class IOCStatus(str, Enum):
    """Status of an IOC in the database."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    REVIEWED = "reviewed"
    FALSE_POSITIVE = "false_positive"


# =============================================================================
# Domain Models
# =============================================================================


class ThreatIOC(SQLModel, table=True):
    """
    Indicator of Compromise - the core IOC database entity.

    Stores all IOCs with their metadata, confidence scores, and lifecycle.
    """

    __tablename__ = "threat_iocs"

    id: int | None = Field(default=None, primary_key=True)
    ioc_value: str = Field(
        index=True, nullable=False, sa_type=Text, description="The IOC value (IP, domain, URL, hash, etc.)"
    )
    ioc_type: IOCType = Field(
        index=True, nullable=False, description="Type of IOC"
    )
    threat_category: ThreatCategory = Field(
        default=ThreatCategory.UNKNOWN,
        index=True,
        nullable=False,
        description="Threat classification category",
    )
    status: IOCStatus = Field(
        default=IOCStatus.ACTIVE, index=True, nullable=False
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence score (0-1)"
    )
    severity: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Severity score (0-1)"
    )
    risk_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Composite risk score (0-1)"
    )
    source: ThreatFeedSource = Field(
        default=ThreatFeedSource.INTERNAL_ANALYSIS,
        index=True,
        nullable=False,
    )
    source_reference: str | None = Field(
        default=None, description="Reference URL or ID from the source"
    )
    first_seen: datetime = Field(
        default_factory=_utcnow, nullable=False, index=True
    )
    last_seen: datetime = Field(
        default_factory=_utcnow, nullable=False, index=True
    )
    expires_at: datetime | None = Field(default=None)
    country_code: str | None = Field(
        default=None, max_length=5, index=True
    )
    asn: str | None = Field(default=None, max_length=20)
    asn_org: str | None = Field(default=None)
    isp: str | None = Field(default=None)
    domain_registrar: str | None = Field(default=None)
    domain_created: datetime | None = Field(default=None)
    domain_expires: datetime | None = Field(default=None)
    reverse_dns: str | None = Field(default=None)
    tags: str | None = Field(
        default=None, description="Comma-separated tags"
    )
    extra_data: dict | None = Field(
        default=None, sa_type=JSON, description="Additional metadata as JSON"
    )
    notes: str | None = Field(default=None, sa_type=Text)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime | None = Field(
        default=None,
        sa_column_kwargs={"onupdate": _utcnow},
    )

    # Relationships
    analyses: list["ThreatAnalysis"] = Relationship(back_populates="ioc")


class ThreatFeed(SQLModel, table=True):
    """
    Threat feed tracking entity.

    Tracks each feed source, its last update, status, and statistics.
    """

    __tablename__ = "threat_feeds"

    id: int | None = Field(default=None, primary_key=True)
    source: ThreatFeedSource = Field(
        index=True, nullable=False, unique=True
    )
    name: str = Field(nullable=False)
    enabled: bool = Field(default=True, index=True)
    last_update: datetime | None = Field(default=None)
    next_update: datetime | None = Field(default=None)
    update_interval: int = Field(
        default=3600, description="Update interval in seconds"
    )
    total_iocs_imported: int = Field(default=0)
    total_iocs_active: int = Field(default=0)
    last_error: str | None = Field(default=None, sa_type=Text)
    consecutive_failures: int = Field(default=0)
    status: str = Field(default="idle", max_length=50)  # idle, updating, error
    feed_metadata: dict | None = Field(
        default=None, sa_type=JSON, description="Feed metadata"
    )
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime | None = Field(
        default=None,
        sa_column_kwargs={"onupdate": _utcnow},
    )


class ThreatAnalysis(SQLModel, table=True):
    """
    Record of a threat intelligence analysis request.

    Stores the full analysis result including all provider responses.
    """

    __tablename__ = "threat_analyses"

    id: int | None = Field(default=None, primary_key=True)
    ioc_id: int | None = Field(
        default=None,
        foreign_key="threat_iocs.id",
        index=True,
    )
    query_value: str = Field(
        nullable=False, index=True, sa_type=Text
    )
    query_type: IOCType = Field(
        nullable=False, index=True
    )
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_level: RiskLevel = Field(
        default=RiskLevel.UNKNOWN, index=True
    )
    threat_category: ThreatCategory = Field(
        default=ThreatCategory.UNKNOWN, index=True
    )
    is_malicious: bool = Field(default=False, index=True)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sources_checked: int = Field(default=0)
    positive_detections: int = Field(default=0)
    total_detections: int = Field(default=0)
    provider_results: dict | None = Field(
        default=None, sa_type=JSON, description="Results from each provider"
    )
    geoip_data: dict | None = Field(
        default=None, sa_type=JSON
    )
    dns_data: dict | None = Field(default=None, sa_type=JSON)
    whois_data: dict | None = Field(default=None, sa_type=JSON)
    asn_data: dict | None = Field(default=None, sa_type=JSON)
    explanation: str | None = Field(default=None, sa_type=Text)
    tags: str | None = Field(default=None)
    source: str = Field(default="api", max_length=50)
    user_id: int | None = Field(
        default=None, foreign_key="users.id", index=True
    )
    processing_time_ms: float = Field(default=0.0)
    created_at: datetime = Field(
        default_factory=_utcnow, nullable=False, index=True
    )

    # Relationships
    ioc: Optional["ThreatIOC"] = Relationship(back_populates="analyses")


class ThreatTimelineEntry(SQLModel, table=True):
    """
    Timeline entry for threat events.

    Provides a chronological view of threat intelligence events.
    """

    __tablename__ = "threat_timeline"

    id: int | None = Field(default=None, primary_key=True)
    event_type: str = Field(
        nullable=False, index=True, max_length=100
    )  # ioc_added, feed_updated, analysis_completed, etc.
    description: str = Field(nullable=False, sa_type=Text)
    severity: RiskLevel = Field(
        default=RiskLevel.INFO, index=True
    )
    ioc_id: int | None = Field(
        default=None, foreign_key="threat_iocs.id", index=True
    )
    feed_id: int | None = Field(
        default=None, foreign_key="threat_feeds.id", index=True
    )
    analysis_id: int | None = Field(
        default=None, foreign_key="threat_analyses.id", index=True
    )
    extra_data: dict | None = Field(
        default=None, sa_type=JSON
    )
    created_at: datetime = Field(
        default_factory=_utcnow, nullable=False, index=True
    )


class ThreatRiskScore(SQLModel, table=True):
    """
    Aggregate risk score calculation record.

    Stores historical risk score calculations for trend analysis.
    """

    __tablename__ = "threat_risk_scores"

    id: int | None = Field(default=None, primary_key=True)
    ioc_id: int | None = Field(
        default=None, foreign_key="threat_iocs.id", index=True
    )
    score_value: float = Field(nullable=False, ge=0.0, le=1.0)
    score_components: dict | None = Field(
        default=None, sa_type=JSON,
        description="Breakdown of scores from each component",
    )
    calculation_version: str = Field(default="1.0", max_length=20)
    risk_level: RiskLevel = Field(
        default=RiskLevel.UNKNOWN, index=True
    )
    created_at: datetime = Field(
        default_factory=_utcnow, nullable=False, index=True
    )

