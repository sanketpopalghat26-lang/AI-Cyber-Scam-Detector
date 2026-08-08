"""Tests for investigation database models."""
from backend.app.investigation.models import (
    CaseAttachment,
    CaseNote,
    CasePriority,
    CaseStatus,
    CaseType,
    Evidence,
    EvidenceType,
    InvestigationCase,
    InvestigationHistory,
)


class TestInvestigationCase:
    def test_create_case(self):
        case = InvestigationCase(
            title="Test phishing case",
            description="A test case",
            case_type=CaseType.PHISHING,
            priority=CasePriority.HIGH,
            created_by=1,
        )
        assert case.title == "Test phishing case"
        assert case.case_type == CaseType.PHISHING
        assert case.priority == CasePriority.HIGH
        assert case.status == CaseStatus.OPEN
        assert not case.is_archived

    def test_case_default_status(self):
        case = InvestigationCase(title="Default", created_by=1)
        assert case.status == CaseStatus.OPEN

    def test_case_default_priority(self):
        case = InvestigationCase(title="Default", created_by=1)
        assert case.priority == CasePriority.MEDIUM

    def test_case_with_scan_relation(self):
        case = InvestigationCase(
            title="Related case",
            created_by=1,
            related_scan_id=42,
        )
        assert case.related_scan_id == 42

    def test_case_with_financials(self):
        case = InvestigationCase(
            title="Financial fraud",
            created_by=1,
            financial_loss_estimate=50000.00,
            affected_users_count=150,
        )
        assert case.financial_loss_estimate == 50000.00
        assert case.affected_users_count == 150


class TestEvidence:
    def test_create_evidence(self):
        evidence = Evidence(
            case_id=1,
            evidence_type=EvidenceType.EMAIL,
            title="Suspicious email",
            content="Full email content",
            collected_by=1,
        )
        assert evidence.case_id == 1
        assert evidence.evidence_type == EvidenceType.EMAIL
        assert not evidence.is_verified

    def test_verified_evidence(self):
        evidence = Evidence(
            case_id=1,
            evidence_type=EvidenceType.SCREENSHOT,
            title="Screenshot",
            collected_by=1,
            is_verified=True,
            verified_by=2,
        )
        assert evidence.is_verified
        assert evidence.verified_by == 2


class TestCaseNote:
    def test_create_note(self):
        note = CaseNote(
            case_id=1,
            content="Investigation note",
            created_by=1,
        )
        assert note.case_id == 1
        assert note.content == "Investigation note"
        assert not note.is_internal

    def test_internal_note(self):
        note = CaseNote(
            case_id=1,
            content="Internal note",
            created_by=1,
            is_internal=True,
        )
        assert note.is_internal


class TestCaseAttachment:
    def test_create_attachment(self):
        attachment = CaseAttachment(
            case_id=1,
            filename="report.pdf",
            file_path="/attachments/report.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024000,
            uploaded_by=1,
        )
        assert attachment.filename == "report.pdf"
        assert attachment.file_size_bytes == 1024000


class TestInvestigationHistory:
    def test_create_history(self):
        entry = InvestigationHistory(
            case_id=1,
            action="case.created",
            description="Case created",
            performed_by=1,
        )
        assert entry.action == "case.created"
        assert entry.performed_by == 1


class TestEnums:
    def test_case_status_values(self):
        assert CaseStatus.OPEN.value == "open"
        assert CaseStatus.IN_PROGRESS.value == "in_progress"
        assert CaseStatus.RESOLVED.value == "resolved"
        assert CaseStatus.CLOSED.value == "closed"

    def test_case_priority_values(self):
        assert CasePriority.LOW.value == "low"
        assert CasePriority.MEDIUM.value == "medium"
        assert CasePriority.HIGH.value == "high"
        assert CasePriority.CRITICAL.value == "critical"

    def test_case_type_values(self):
        assert CaseType.PHISHING.value == "phishing"
        assert CaseType.FRAUD.value == "fraud"
        assert CaseType.SCAM.value == "scam"

    def test_evidence_type_values(self):
        assert EvidenceType.EMAIL.value == "email"
        assert EvidenceType.SCREENSHOT.value == "screenshot"
        assert EvidenceType.URL.value == "url"

