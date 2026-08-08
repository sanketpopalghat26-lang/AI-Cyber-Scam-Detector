"""
Investigation Database Models
===============================
SQLModel ORM models for case management, evidence, and investigation tracking.
"""

import enum
from datetime import UTC, datetime

from sqlmodel import Field, Relationship, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class CaseStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"


class CasePriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CaseType(str, enum.Enum):
    PHISHING = "phishing"
    FRAUD = "fraud"
    SCAM = "scam"
    MALWARE = "malware"
    SOCIAL_ENGINEERING = "social_engineering"
    IDENTITY_THEFT = "identity_theft"
    FINANCIAL_FRAUD = "financial_fraud"
    OTHER = "other"


class EvidenceType(str, enum.Enum):
    SCREENSHOT = "screenshot"
    EMAIL = "email"
    URL = "url"
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    LOG = "log"
    OTHER = "other"


class InvestigationCase(SQLModel, table=True):
    __tablename__ = "investigation_cases"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(nullable=False, max_length=500)
    description: str = Field(default="", max_length=10000)
    case_type: CaseType = Field(default=CaseType.OTHER)
    status: CaseStatus = Field(default=CaseStatus.OPEN, index=True)
    priority: CasePriority = Field(default=CasePriority.MEDIUM, index=True)
    assigned_to: int | None = Field(default=None, foreign_key="users.id", index=True)
    created_by: int = Field(foreign_key="users.id", index=True)
    related_scan_id: int | None = Field(default=None, foreign_key="scans.id")
    related_threat_id: int | None = Field(default=None, foreign_key="threat_iocs.id")
    tags: str = Field(default="", max_length=2000)
    findings: str = Field(default="", max_length=50000)
    resolution_notes: str = Field(default="", max_length=10000)
    financial_loss_estimate: float | None = Field(default=None)
    affected_users_count: int | None = Field(default=None)
    is_archived: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    updated_at: datetime | None = Field(default=None, sa_column_kwargs={"onupdate": _utcnow})
    resolved_at: datetime | None = Field(default=None)
    closed_at: datetime | None = Field(default=None)

    # Relationships
    evidence_items: list["Evidence"] = Relationship(back_populates="case")
    notes: list["CaseNote"] = Relationship(back_populates="case")
    attachments: list["CaseAttachment"] = Relationship(back_populates="case")
    history: list["InvestigationHistory"] = Relationship(back_populates="case")


class Evidence(SQLModel, table=True):
    __tablename__ = "investigation_evidence"

    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="investigation_cases.id", index=True)
    evidence_type: EvidenceType = Field(default=EvidenceType.OTHER)
    title: str = Field(nullable=False, max_length=500)
    description: str = Field(default="", max_length=5000)
    content: str = Field(default="", max_length=50000)
    source: str = Field(default="", max_length=500)
    collected_by: int = Field(foreign_key="users.id")
    collected_at: datetime = Field(default_factory=_utcnow)
    metadata_json: str = Field(default="{}", max_length=10000)
    hash_value: str | None = Field(default=None, max_length=128)
    is_verified: bool = Field(default=False)
    verified_by: int | None = Field(default=None, foreign_key="users.id")
    verified_at: datetime | None = Field(default=None)

    # Relationships
    case: InvestigationCase = Relationship(back_populates="evidence_items")


class CaseNote(SQLModel, table=True):
    __tablename__ = "investigation_notes"

    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="investigation_cases.id", index=True)
    content: str = Field(nullable=False, max_length=10000)
    created_by: int = Field(foreign_key="users.id")
    is_internal: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime | None = Field(default=None, sa_column_kwargs={"onupdate": _utcnow})

    # Relationships
    case: InvestigationCase = Relationship(back_populates="notes")


class CaseAttachment(SQLModel, table=True):
    __tablename__ = "investigation_attachments"

    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="investigation_cases.id", index=True)
    filename: str = Field(nullable=False, max_length=500)
    file_path: str = Field(nullable=False, max_length=1000)
    mime_type: str = Field(default="application/octet-stream", max_length=100)
    file_size_bytes: int = Field(default=0)
    uploaded_by: int = Field(foreign_key="users.id")
    description: str = Field(default="", max_length=2000)
    created_at: datetime = Field(default_factory=_utcnow)

    # Relationships
    case: InvestigationCase = Relationship(back_populates="attachments")


class InvestigationHistory(SQLModel, table=True):
    __tablename__ = "investigation_history"

    id: int | None = Field(default=None, primary_key=True)
    case_id: int = Field(foreign_key="investigation_cases.id", index=True)
    action: str = Field(nullable=False, max_length=200)
    description: str = Field(default="", max_length=5000)
    previous_value: str = Field(default="", max_length=2000)
    new_value: str = Field(default="", max_length=2000)
    performed_by: int = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=_utcnow, index=True)

    # Relationships
    case: InvestigationCase = Relationship(back_populates="history")

