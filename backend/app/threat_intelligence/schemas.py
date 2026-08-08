"""
Threat Intelligence API Schemas
=================================
Pydantic models for request/response validation for the Threat Intelligence Center.
Implements strict input validation and sanitization with OpenAPI documentation.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import (
    IOCStatus,
    IOCType,
    RiskLevel,
    ThreatCategory,
    ThreatFeedSource,
)

# =============================================================================
# Request Schemas
# =============================================================================


class ThreatSearchParams(BaseModel):
    """Search parameters for IOC database queries."""

    query: str = Field(
        ..., min_length=1, max_length=500,
        description="Search query (IP, domain, URL, hash, or keyword)",
        examples=["192.168.1.1", "example.com", "https://phishing.com/login"],
    )
    ioc_type: IOCType | None = Field(
        default=None,
        description="Filter by IOC type",
    )
    threat_category: ThreatCategory | None = Field(
        default=None,
        description="Filter by threat category",
    )
    risk_level: RiskLevel | None = Field(
        default=None,
        description="Filter by minimum risk level",
    )
    status: IOCStatus | None = Field(
        default=None,
        description="Filter by IOC status",
    )
    source: ThreatFeedSource | None = Field(
        default=None,
        description="Filter by feed source",
    )
    limit: int = Field(
        default=50, ge=1, le=1000,
        description="Maximum number of results",
    )
    offset: int = Field(
        default=0, ge=0,
        description="Number of results to skip",
    )
    include_expired: bool = Field(
        default=False,
        description="Include expired IOCs in results",
    )

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        """Sanitize and normalize the search query."""
        v = v.strip().lower()
        if not v:
            raise ValueError("Query must not be empty")
        # Remove null bytes
        v = v.replace("\x00", "")
        return v


class ThreatAnalyzeRequest(BaseModel):
    """Request to analyze a potential threat."""

    value: str = Field(
        ..., min_length=1, max_length=2000,
        description="The value to analyze (IP, domain, URL, email, hash)",
        examples=[
            "192.168.1.1",
            "suspicious-bank.com",
            "https://phishing-site.com/login",
            "d41d8cd98f00b204e9800998ecf8427e",
        ],
    )
    value_type: IOCType | None = Field(
        default=None,
        description="Type of the value to analyze. Auto-detected if not provided.",
    )
    source: str = Field(
        default="api",
        max_length=50,
        description="Source of the analysis request",
    )
    check_virustotal: bool = Field(default=True)
    check_abuseipdb: bool = Field(default=True)
    check_phishtank: bool = Field(default=True)
    check_openphish: bool = Field(default=True)
    check_alienvault: bool = Field(default=True)
    check_dns: bool = Field(default=True)
    check_whois: bool = Field(default=True)
    check_geoip: bool = Field(default=True)
    check_asn: bool = Field(default=True)

    @field_validator("value")
    @classmethod
    def sanitize_value(cls, v: str) -> str:
        """Sanitize the value."""
        v = v.strip()
        if not v:
            raise ValueError("Value must not be empty")
        v = v.replace("\x00", "")
        return v


# =============================================================================
# Response Schemas
# =============================================================================


class IOCEntry(BaseModel):
    """An IOC entry from the database."""

    id: int
    ioc_value: str
    ioc_type: IOCType
    threat_category: ThreatCategory
    status: IOCStatus
    confidence: float
    severity: float
    risk_score: float
    source: ThreatFeedSource
    source_reference: str | None = None
    first_seen: str
    last_seen: str
    expires_at: str | None = None
    country_code: str | None = None
    asn: str | None = None
    asn_org: str | None = None
    isp: str | None = None
    tags: str | None = None
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ThreatSearchResponse(BaseModel):
    """Response for IOC search queries."""

    total: int = Field(..., description="Total number of matching results")
    results: list[IOCEntry] = Field(
        default_factory=list, description="Matching IOC entries"
    )
    query: str = Field(..., description="The original search query")
    limit: int = Field(..., description="Maximum results limit")
    offset: int = Field(..., description="Results offset")
    has_more: bool = Field(
        ..., description="Whether there are more results available"
    )
    search_time_ms: float = Field(
        ..., description="Search execution time in milliseconds"
    )


class ThreatStatsResponse(BaseModel):
    """Statistics about the IOC database."""

    total_iocs: int = Field(..., description="Total number of IOCs")
    active_iocs: int = Field(..., description="Number of active IOCs")
    by_type: dict[str, int] = Field(
        default_factory=dict, description="IOC count by type"
    )
    by_category: dict[str, int] = Field(
        default_factory=dict, description="IOC count by threat category"
    )
    by_risk_level: dict[str, int] = Field(
        default_factory=dict, description="IOC count by risk level"
    )
    by_source: dict[str, int] = Field(
        default_factory=dict, description="IOC count by feed source"
    )
    total_analyses: int = Field(
        default=0, description="Total analyses performed"
    )
    malicious_percentage: float = Field(
        default=0.0, description="Percentage of IOCs marked malicious"
    )
    feed_status: list[dict[str, Any]] = Field(
        default_factory=list, description="Status of each threat feed"
    )
    top_countries: list[dict[str, Any]] = Field(
        default_factory=list, description="Top countries by IOC count"
    )
    top_asns: list[dict[str, Any]] = Field(
        default_factory=list, description="Top ASNs by IOC count"
    )
    recent_activity: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Recent threat timeline activity",
    )
    last_updated: str = Field(
        ..., description="When the statistics were last calculated"
    )


class ProviderResult(BaseModel):
    """Result from a single threat intelligence provider."""

    provider: str = Field(..., description="Provider name")
    success: bool = Field(..., description="Whether the check succeeded")
    malicious: bool = Field(
        default=False, description="Whether the provider flagged as malicious"
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Confidence score from this provider",
    )
    details: dict[str, Any] | None = Field(
        default=None, description="Provider-specific details"
    )
    error: str | None = Field(
        default=None, description="Error message if check failed"
    )
    response_time_ms: float = Field(
        default=0.0, description="Response time in milliseconds"
    )


class ThreatAnalyzeResponse(BaseModel):
    """Response from a full threat analysis."""

    id: int = Field(..., description="Analysis record ID")
    value: str = Field(..., description="The analyzed value")
    value_type: IOCType = Field(..., description="Type of the analyzed value")
    is_malicious: bool = Field(
        ..., description="Overall malicious classification"
    )
    risk_score: float = Field(
        ..., ge=0.0, le=1.0, description="Composite risk score (0-1)"
    )
    risk_level: RiskLevel = Field(
        ..., description="Risk level classification"
    )
    threat_category: ThreatCategory = Field(
        ..., description="Threat category classification"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Overall confidence score"
    )
    sources_checked: int = Field(
        ..., description="Number of providers checked"
    )
    positive_detections: int = Field(
        ..., description="Number of providers flagging as malicious"
    )
    total_detections: int = Field(
        ..., description="Total detections across providers"
    )
    provider_results: list[ProviderResult] = Field(
        default_factory=list,
        description="Results from each provider",
    )
    geoip: dict[str, Any] | None = Field(
        default=None, description="GeoIP analysis data"
    )
    dns: dict[str, Any] | None = Field(
        default=None, description="DNS analysis data"
    )
    whois: dict[str, Any] | None = Field(
        default=None, description="WHOIS lookup data"
    )
    asn: dict[str, Any] | None = Field(
        default=None, description="ASN lookup data"
    )
    explanation: str = Field(
        ..., description="Human-readable explanation of the analysis"
    )
    tags: list[str] = Field(
        default_factory=list, description="Tags from the analysis"
    )
    processing_time_ms: float = Field(
        ..., description="Total processing time in milliseconds"
    )
    created_at: str = Field(
        ..., description="When the analysis was performed"
    )


class ThreatFeedEntry(BaseModel):
    """Status of a threat intelligence feed."""

    id: int
    source: ThreatFeedSource
    name: str
    enabled: bool
    status: str
    last_update: str | None = None
    next_update: str | None = None
    total_iocs_imported: int = 0
    total_iocs_active: int = 0
    consecutive_failures: int = 0
    last_error: str | None = None

    model_config = ConfigDict(from_attributes=True)

