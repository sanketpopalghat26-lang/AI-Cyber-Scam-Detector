"""
Fraud Investigation Dashboard
==============================
Enterprise case management and fraud investigation module.
Provides case lifecycle management, evidence collection,
investigator assignment, and export capabilities.

Feature Flag: ENABLE_INVESTIGATION (default: true)
"""

from .config import InvestigationConfig
from .models import (
    CaseAttachment,
    CaseNote,
    CasePriority,
    CaseStatus,
    CaseType,
    Evidence,
    InvestigationCase,
    InvestigationHistory,
)
from .router import router
from .schemas import (
    CaseCreate,
    CaseListResponse,
    CaseNoteCreate,
    CaseNoteResponse,
    CaseResponse,
    CaseUpdate,
    EvidenceCreate,
    EvidenceResponse,
    InvestigationStats,
)
from .service import InvestigationService

__all__ = [
    "InvestigationConfig",
    "InvestigationCase",
    "Evidence",
    "CaseNote",
    "CaseAttachment",
    "InvestigationHistory",
    "CaseStatus",
    "CasePriority",
    "CaseType",
    "CaseCreate",
    "CaseUpdate",
    "CaseResponse",
    "CaseListResponse",
    "EvidenceCreate",
    "EvidenceResponse",
    "CaseNoteCreate",
    "CaseNoteResponse",
    "InvestigationStats",
    "InvestigationService",
    "router",
]

