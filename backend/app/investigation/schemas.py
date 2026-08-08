"""
Investigation API Schemas
===========================
Pydantic models for request/response validation.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import CasePriority, CaseStatus, CaseType, EvidenceType

# =============================================================================
# Case Schemas
# =============================================================================

class CaseCreate(BaseModel):
    """Create a new investigation case."""
    title: str = Field(..., min_length=1, max_length=500, description="Case title")
    description: str = Field("", max_length=10000, description="Case description")
    case_type: CaseType = Field(default=CaseType.OTHER, description="Type of case")
    priority: CasePriority = Field(default=CasePriority.MEDIUM, description="Case priority")
    assigned_to: int | None = Field(default=None, description="Investigator user ID")
    related_scan_id: int | None = Field(default=None, description="Related scan ID")
    related_threat_id: int | None = Field(default=None, description="Related threat IOC ID")
    tags: str = Field("", max_length=2000, description="Comma-separated tags")
    financial_loss_estimate: float | None = Field(default=None, ge=0, description="Estimated financial loss")
    affected_users_count: int | None = Field(default=None, ge=0, description="Number of affected users")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        return v.strip()

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: str) -> str:
        if v:
            tags = [t.strip() for t in v.split(",") if t.strip()]
            return ",".join(tags[:20])
        return v


class CaseUpdate(BaseModel):
    """Update an existing investigation case."""
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=10000)
    status: CaseStatus | None = Field(default=None)
    priority: CasePriority | None = Field(default=None)
    assigned_to: int | None = Field(default=None)
    tags: str | None = Field(default=None, max_length=2000)
    findings: str | None = Field(default=None, max_length=50000)
    resolution_notes: str | None = Field(default=None, max_length=10000)
    financial_loss_estimate: float | None = Field(default=None, ge=0)
    affected_users_count: int | None = Field(default=None, ge=0)
    is_archived: bool | None = Field(default=None)


class CaseResponse(BaseModel):
    """Full case details response."""
    id: int
    title: str
    description: str
    case_type: CaseType
    status: CaseStatus
    priority: CasePriority
    assigned_to: int | None = None
    created_by: int
    related_scan_id: int | None = None
    related_threat_id: int | None = None
    tags: str
    findings: str
    resolution_notes: str
    financial_loss_estimate: float | None = None
    affected_users_count: int | None = None
    is_archived: bool
    evidence_count: int = 0
    notes_count: int = 0
    created_at: str
    updated_at: str | None = None
    resolved_at: str | None = None
    closed_at: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CaseListResponse(BaseModel):
    """Paginated case list response."""
    items: list[CaseResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# =============================================================================
# Evidence Schemas
# =============================================================================

class EvidenceCreate(BaseModel):
    """Add evidence to a case."""
    evidence_type: EvidenceType = Field(default=EvidenceType.OTHER)
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field("", max_length=5000)
    content: str = Field("", max_length=50000)
    source: str = Field("", max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        return v.strip()


class EvidenceResponse(BaseModel):
    """Evidence details response."""
    id: int
    case_id: int
    evidence_type: EvidenceType
    title: str
    description: str
    content: str
    source: str
    collected_by: int
    collected_at: str
    hash_value: str | None = None
    is_verified: bool
    verified_by: int | None = None
    verified_at: str | None = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Note Schemas
# =============================================================================

class CaseNoteCreate(BaseModel):
    """Add a note to a case."""
    content: str = Field(..., min_length=1, max_length=10000)
    is_internal: bool = Field(default=False, description="Internal notes visible only to investigators")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        return v.strip()


class CaseNoteResponse(BaseModel):
    """Note details response."""
    id: int
    case_id: int
    content: str
    created_by: int
    is_internal: bool
    created_at: str
    updated_at: str | None = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Stats Schemas
# =============================================================================

class InvestigationStats(BaseModel):
    """Investigation dashboard statistics."""
    total_cases: int = 0
    open_cases: int = 0
    in_progress_cases: int = 0
    resolved_cases: int = 0
    closed_cases: int = 0
    critical_cases: int = 0
    high_priority_cases: int = 0
    total_evidence: int = 0
    unverified_evidence: int = 0
    cases_by_type: dict[str, int] = Field(default_factory=dict)
    cases_by_priority: dict[str, int] = Field(default_factory=dict)
    recent_cases: list[CaseResponse] = Field(default_factory=list)

