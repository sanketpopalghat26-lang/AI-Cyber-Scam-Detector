"""
Investigation Module Configuration
====================================
"""

import os
from dataclasses import dataclass, field


@dataclass
class InvestigationConfig:
    """Configuration for the Investigation module."""

    enabled: bool = True
    max_evidence_per_case: int = 100
    max_notes_per_case: int = 500
    max_attachments_per_case: int = 50
    max_attachment_size_mb: int = 50
    default_page_size: int = 20
    max_page_size: int = 100
    export_pdf_enabled: bool = True
    export_csv_enabled: bool = True
    evidence_retention_days: int = 365
    auto_close_days: int = 90
    allowed_mime_types: list[str] = field(default_factory=lambda: [
        "application/pdf", "image/png", "image/jpeg", "image/gif",
        "text/plain", "text/csv", "application/json",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ])

    @classmethod
    def from_env(cls) -> "InvestigationConfig":
        return cls(
            enabled=os.getenv("ENABLE_INVESTIGATION", "true").lower() == "true",
            max_evidence_per_case=int(os.getenv("INVESTIGATION_MAX_EVIDENCE", "100")),
            max_notes_per_case=int(os.getenv("INVESTIGATION_MAX_NOTES", "500")),
            max_attachment_size_mb=int(os.getenv("INVESTIGATION_MAX_ATTACHMENT_MB", "50")),
            default_page_size=int(os.getenv("INVESTIGATION_PAGE_SIZE", "20")),
        )
