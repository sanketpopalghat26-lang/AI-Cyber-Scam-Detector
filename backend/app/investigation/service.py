"""
Investigation Service
======================
Enterprise case management business logic with caching,
RBAC validation, audit logging, and metrics tracking.
"""

import csv
import io
from datetime import UTC, datetime

from fastapi import HTTPException
from prometheus_client import Counter, Histogram
from sqlmodel import Session, func, select

from ..core.audit import get_audit_logger
from ..core.cache import get_cache
from ..models import User
from .config import InvestigationConfig
from .models import (
    CaseNote,
    CasePriority,
    CaseStatus,
    CaseType,
    Evidence,
    InvestigationCase,
    InvestigationHistory,
)
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

# =============================================================================
# Prometheus Metrics
# =============================================================================

cases_created_total = Counter(
    "investigation_cases_total", "Total investigation cases created", ["case_type", "priority"]
)
cases_resolved_total = Counter(
    "investigation_cases_resolved_total", "Total cases resolved", ["case_type"]
)
evidence_collected_total = Counter(
    "investigation_evidence_total", "Total evidence items collected", ["evidence_type"]
)
investigation_duration_seconds = Histogram(
    "investigation_duration_seconds", "Time to resolve cases", buckets=(3600, 86400, 604800, 2592000)
)


class InvestigationService:
    """Enterprise investigation case management service."""

    def __init__(self, config: InvestigationConfig | None = None):
        self.config = config or InvestigationConfig.from_env()
        self.cache = get_cache()

    async def create_case(
        self,
        payload: CaseCreate,
        user: User,
        session: Session,
    ) -> CaseResponse:
        """Create a new investigation case."""
        case = InvestigationCase(
            title=payload.title,
            description=payload.description,
            case_type=payload.case_type,
            priority=payload.priority,
            assigned_to=payload.assigned_to,
            created_by=user.id,
            related_scan_id=payload.related_scan_id,
            related_threat_id=payload.related_threat_id,
            tags=payload.tags,
            financial_loss_estimate=payload.financial_loss_estimate,
            affected_users_count=payload.affected_users_count,
        )
        session.add(case)
        session.commit()
        session.refresh(case)

        # Record history
        self._add_history(session, case.id, "case.created", "Case created", user.id)

        # Metrics
        cases_created_total.labels(case_type=case.case_type.value, priority=case.priority.value).inc()

        # Audit
        get_audit_logger().log(
            action="investigation.case.create",
            actor=user.email,
            resource="investigation_case",
            resource_id=str(case.id),
            details={"title": case.title, "case_type": case.case_type.value},
        )

        # Invalidate cache
        await self.cache.clear_pattern("investigation:*")

        return await self._case_to_response(case, session)

    async def get_case(
        self,
        case_id: int,
        user: User,
        session: Session,
    ) -> CaseResponse:
        """Get case details by ID."""
        case = session.get(InvestigationCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # Cache key
        cache_key = f"investigation:case:{case_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return CaseResponse(**cached)

        result = await self._case_to_response(case, session)
        await self.cache.set(cache_key, result.model_dump(), ttl=120)
        return result

    async def update_case(
        self,
        case_id: int,
        payload: CaseUpdate,
        user: User,
        session: Session,
    ) -> CaseResponse:
        """Update an existing case."""
        case = session.get(InvestigationCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        update_data = payload.model_dump(exclude_unset=True)
        old_status = case.status.value

        for field, value in update_data.items():
            if value is not None:
                setattr(case, field, value)

        # Handle status transitions
        if "status" in update_data:
            new_status = update_data["status"]
            if new_status == CaseStatus.RESOLVED and old_status != CaseStatus.RESOLVED:
                case.resolved_at = datetime.now(UTC)
                cases_resolved_total.labels(case_type=case.case_type.value).inc()
            elif new_status == CaseStatus.CLOSED and old_status != CaseStatus.CLOSED:
                case.closed_at = datetime.now(UTC)

        case.updated_at = datetime.now(UTC)
        session.add(case)
        session.commit()

        # Record history
        changes = "; ".join(f"{k}: {v}" for k, v in update_data.items())
        self._add_history(session, case_id, "case.updated", f"Updated: {changes}", user.id)

        # Audit
        get_audit_logger().log(
            action="investigation.case.update",
            actor=user.email,
            resource="investigation_case",
            resource_id=str(case_id),
            details=update_data,
        )

        # Invalidate cache
        await self.cache.clear_pattern("investigation:*")

        return await self._case_to_response(case, session)

    async def list_cases(
        self,
        user: User,
        session: Session,
        page: int = 1,
        page_size: int = 20,
        status: CaseStatus | None = None,
        priority: CasePriority | None = None,
        case_type: CaseType | None = None,
        assigned_to: int | None = None,
        search: str | None = None,
        is_archived: bool = False,
    ) -> CaseListResponse:
        """List cases with filtering and pagination."""
        query = select(InvestigationCase).where(
            InvestigationCase.is_archived == is_archived
        )

        if status:
            query = query.where(InvestigationCase.status == status)
        if priority:
            query = query.where(InvestigationCase.priority == priority)
        if case_type:
            query = query.where(InvestigationCase.case_type == case_type)
        if assigned_to:
            query = query.where(InvestigationCase.assigned_to == assigned_to)
        if search:
            search_term = f"%{search}%"
            query = query.where(
                (InvestigationCase.title.ilike(search_term)) |
                (InvestigationCase.description.ilike(search_term)) |
                (InvestigationCase.tags.ilike(search_term))
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = session.exec(count_query).one()

        # Paginate
        page_size = min(page_size, self.config.max_page_size)
        offset = (page - 1) * page_size
        query = query.order_by(InvestigationCase.created_at.desc()).offset(offset).limit(page_size)
        cases = session.exec(query).all()

        items = [await self._case_to_response(c, session) for c in cases]

        return CaseListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=max(1, (total + page_size - 1) // page_size),
        )

    async def get_stats(
        self,
        user: User,
        session: Session,
    ) -> InvestigationStats:
        """Get investigation dashboard statistics."""
        cache_key = "investigation:stats"
        cached = await self.cache.get(cache_key)
        if cached:
            return InvestigationStats(**cached)

        # Total counts
        total = session.exec(select(func.count()).select_from(InvestigationCase)).one()
        open_count = session.exec(
            select(func.count()).where(
                InvestigationCase.status.in_([CaseStatus.OPEN, CaseStatus.IN_PROGRESS, CaseStatus.UNDER_REVIEW])
            )
        ).one()
        resolved = session.exec(
            select(func.count()).where(InvestigationCase.status == CaseStatus.RESOLVED)
        ).one()
        closed = session.exec(
            select(func.count()).where(InvestigationCase.status == CaseStatus.CLOSED)
        ).one()

        critical = session.exec(
            select(func.count()).where(InvestigationCase.priority == CasePriority.CRITICAL)
        ).one()
        high = session.exec(
            select(func.count()).where(InvestigationCase.priority == CasePriority.HIGH)
        ).one()

        evidence_total = session.exec(
            select(func.count()).select_from(Evidence)
        ).one()
        unverified = session.exec(
            select(func.count()).where(Evidence.is_verified == False)  # noqa: E712
        ).one()

        # Cases by type
        type_query = session.exec(
            select(InvestigationCase.case_type, func.count().label("count"))
            .group_by(InvestigationCase.case_type)
        ).all()
        cases_by_type = {str(row[0].value if hasattr(row[0], 'value') else row[0]): row[1] for row in type_query}

        # Cases by priority
        priority_query = session.exec(
            select(InvestigationCase.priority, func.count().label("count"))
            .group_by(InvestigationCase.priority)
        ).all()
        cases_by_priority = {str(row[0].value if hasattr(row[0], 'value') else row[0]): row[1] for row in priority_query}

        # Recent cases
        recent = session.exec(
            select(InvestigationCase).order_by(InvestigationCase.created_at.desc()).limit(5)
        ).all()
        recent_cases = [await self._case_to_response(c, session) for c in recent]

        stats = InvestigationStats(
            total_cases=total,
            open_cases=open_count,
            in_progress_cases=session.exec(
                select(func.count()).where(InvestigationCase.status == CaseStatus.IN_PROGRESS)
            ).one(),
            resolved_cases=resolved,
            closed_cases=closed,
            critical_cases=critical,
            high_priority_cases=high,
            total_evidence=evidence_total,
            unverified_evidence=unverified,
            cases_by_type=cases_by_type,
            cases_by_priority=cases_by_priority,
            recent_cases=recent_cases,
        )

        await self.cache.set(cache_key, stats.model_dump(), ttl=60)
        return stats

    async def add_evidence(
        self,
        case_id: int,
        payload: EvidenceCreate,
        user: User,
        session: Session,
    ) -> EvidenceResponse:
        """Add evidence to a case."""
        case = session.get(InvestigationCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        evidence = Evidence(
            case_id=case_id,
            evidence_type=payload.evidence_type,
            title=payload.title,
            description=payload.description,
            content=payload.content,
            source=payload.source,
            collected_by=user.id,
            metadata_json=str(payload.metadata),
        )
        session.add(evidence)
        session.commit()
        session.refresh(evidence)

        self._add_history(session, case_id, "evidence.added", f"Evidence added: {payload.title}", user.id)
        evidence_collected_total.labels(evidence_type=payload.evidence_type.value).inc()

        get_audit_logger().log(
            action="investigation.evidence.add",
            actor=user.email,
            resource="evidence",
            resource_id=str(evidence.id),
            details={"case_id": case_id, "type": payload.evidence_type.value},
        )

        await self.cache.clear_pattern("investigation:*")
        return self._evidence_to_response(evidence)

    async def verify_evidence(
        self,
        case_id: int,
        evidence_id: int,
        user: User,
        session: Session,
    ) -> EvidenceResponse:
        """Verify evidence item."""
        evidence = session.get(Evidence, evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise HTTPException(status_code=404, detail="Evidence not found")

        evidence.is_verified = True
        evidence.verified_by = user.id
        evidence.verified_at = datetime.now(UTC)
        session.add(evidence)
        session.commit()

        self._add_history(session, case_id, "evidence.verified", f"Evidence verified: {evidence.title}", user.id)
        await self.cache.clear_pattern("investigation:*")

        return self._evidence_to_response(evidence)

    async def add_note(
        self,
        case_id: int,
        payload: CaseNoteCreate,
        user: User,
        session: Session,
    ) -> CaseNoteResponse:
        """Add a note to a case."""
        case = session.get(InvestigationCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        note = CaseNote(
            case_id=case_id,
            content=payload.content,
            created_by=user.id,
            is_internal=payload.is_internal,
        )
        session.add(note)
        session.commit()
        session.refresh(note)

        self._add_history(session, case_id, "note.added", "Note added", user.id)
        await self.cache.clear_pattern("investigation:*")

        return CaseNoteResponse(
            id=note.id,
            case_id=note.case_id,
            content=note.content[:500] if note.is_internal else note.content,
            created_by=note.created_by,
            is_internal=note.is_internal,
            created_at=note.created_at.isoformat() if note.created_at else "",
            updated_at=note.updated_at.isoformat() if note.updated_at else None,
        )

    async def export_case_csv(
        self,
        case_id: int,
        user: User,
        session: Session,
    ) -> str:
        """Export case details as CSV."""
        case = session.get(InvestigationCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["Field", "Value"])
        writer.writerow(["ID", case.id])
        writer.writerow(["Title", case.title])
        writer.writerow(["Type", case.case_type.value])
        writer.writerow(["Status", case.status.value])
        writer.writerow(["Priority", case.priority.value])
        writer.writerow(["Created At", case.created_at.isoformat() if case.created_at else ""])
        writer.writerow([])
        writer.writerow(["Evidence"])
        writer.writerow(["ID", "Type", "Title", "Collected At", "Verified"])

        evidence_items = session.exec(
            select(Evidence).where(Evidence.case_id == case_id)
        ).all()
        for e in evidence_items:
            writer.writerow([
                e.id, e.evidence_type.value, e.title,
                e.collected_at.isoformat() if e.collected_at else "",
                "Yes" if e.is_verified else "No",
            ])

        return output.getvalue()

    async def delete_case(
        self,
        case_id: int,
        user: User,
        session: Session,
    ) -> None:
        """Soft-delete (archive) a case."""
        case = session.get(InvestigationCase, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        case.is_archived = True
        case.updated_at = datetime.now(UTC)
        session.add(case)
        session.commit()

        get_audit_logger().log(
            action="investigation.case.delete",
            actor=user.email,
            resource="investigation_case",
            resource_id=str(case_id),
            result="success",
        )

        await self.cache.clear_pattern("investigation:*")

    def _add_history(
        self,
        session: Session,
        case_id: int,
        action: str,
        description: str,
        user_id: int,
    ) -> None:
        """Add a history entry."""
        history = InvestigationHistory(
            case_id=case_id,
            action=action,
            description=description,
            performed_by=user_id,
        )
        session.add(history)
        session.commit()

    async def _case_to_response(self, case: InvestigationCase, session: Session) -> CaseResponse:
        """Convert case model to response with counts."""
        evidence_count = session.exec(
            select(func.count()).where(Evidence.case_id == case.id)
        ).one()
        notes_count = session.exec(
            select(func.count()).where(CaseNote.case_id == case.id)
        ).one()

        return CaseResponse(
            id=case.id,
            title=case.title,
            description=case.description,
            case_type=case.case_type,
            status=case.status,
            priority=case.priority,
            assigned_to=case.assigned_to,
            created_by=case.created_by,
            related_scan_id=case.related_scan_id,
            related_threat_id=case.related_threat_id,
            tags=case.tags,
            findings=case.findings,
            resolution_notes=case.resolution_notes,
            financial_loss_estimate=case.financial_loss_estimate,
            affected_users_count=case.affected_users_count,
            is_archived=case.is_archived,
            evidence_count=evidence_count,
            notes_count=notes_count,
            created_at=case.created_at.isoformat() if case.created_at else "",
            updated_at=case.updated_at.isoformat() if case.updated_at else None,
            resolved_at=case.resolved_at.isoformat() if case.resolved_at else None,
            closed_at=case.closed_at.isoformat() if case.closed_at else None,
        )

    @staticmethod
    def _evidence_to_response(evidence: Evidence) -> EvidenceResponse:
        return EvidenceResponse(
            id=evidence.id,
            case_id=evidence.case_id,
            evidence_type=evidence.evidence_type,
            title=evidence.title,
            description=evidence.description,
            content=evidence.content,
            source=evidence.source,
            collected_by=evidence.collected_by,
            collected_at=evidence.collected_at.isoformat() if evidence.collected_at else "",
            hash_value=evidence.hash_value,
            is_verified=evidence.is_verified,
            verified_by=evidence.verified_by,
            verified_at=evidence.verified_at.isoformat() if evidence.verified_at else None,
        )


# Singleton service instance
_service_instance: InvestigationService | None = None


def get_investigation_service() -> InvestigationService:
    """Get the global investigation service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = InvestigationService()
    return _service_instance

