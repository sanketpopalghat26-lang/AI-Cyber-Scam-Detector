"""
Investigation API Router
=========================
REST API endpoints for case management.
Follows Clean Architecture with proper dependency injection.
"""


from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from ..core.db import get_session
from ..models import User
from .models import CasePriority, CaseStatus, CaseType
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
from .service import InvestigationService, get_investigation_service

router = APIRouter(
    prefix="/api/investigation",
    tags=["investigation"],
    responses={404: {"description": "Not found"}},
)

# Bearer token security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user_from_request(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    session: Session = Depends(get_session),
) -> User:
    """Extract current user from bearer token (lazy import to avoid circular deps)."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Lazy import to avoid circular dependency
    token = credentials.credentials
    # Reuse the same logic
    from ..core.security import decode_token
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    email = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    from sqlmodel import select

    from ..models import User as UserModel
    user = session.exec(select(UserModel).where(UserModel.email == email)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# =============================================================================
# Case Endpoints
# =============================================================================

@router.post(
    "/cases",
    response_model=CaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create investigation case",
    description="Create a new fraud investigation case. Requires authentication.",
)
async def create_case(
    payload: CaseCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user_from_request),
    service: InvestigationService = Depends(get_investigation_service),
) -> CaseResponse:
    """Create a new investigation case."""
    return await service.create_case(payload, user, session)


@router.get(
    "/cases",
    response_model=CaseListResponse,
    summary="List investigation cases",
    description="List cases with filtering, search, and pagination.",
)
async def list_cases(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: CaseStatus | None = Query(None, description="Filter by status"),
    priority: CasePriority | None = Query(None, description="Filter by priority"),
    case_type: CaseType | None = Query(None, description="Filter by case type"),
    assigned_to: int | None = Query(None, description="Filter by assignee"),
    search: str | None = Query(None, max_length=200, description="Search in title/description/tags"),
    is_archived: bool = Query(False, description="Include archived cases"),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user_from_request),
    service: InvestigationService = Depends(get_investigation_service),
) -> CaseListResponse:
    """List investigation cases with filters."""
    return await service.list_cases(
        user, session,
        page=page, page_size=page_size,
        status=status, priority=priority,
        case_type=case_type, assigned_to=assigned_to,
        search=search, is_archived=is_archived,
    )


@router.get(
    "/cases/{case_id}",
    response_model=CaseResponse,
    summary="Get case details",
    description="Get detailed information about a specific case.",
)
async def get_case(
    case_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user_from_request),
    service: InvestigationService = Depends(get_investigation_service),
) -> CaseResponse:
    """Get case by ID."""
    return await service.get_case(case_id, user, session)


@router.patch(
    "/cases/{case_id}",
    response_model=CaseResponse,
    summary="Update case",
    description="Update case fields. Supports partial updates.",
)
async def update_case(
    case_id: int,
    payload: CaseUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user_from_request),
    service: InvestigationService = Depends(get_investigation_service),
) -> CaseResponse:
    """Update an existing case."""
    return await service.update_case(case_id, payload, user, session)


@router.delete(
    "/cases/{case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive case",
    description="Soft-delete (archive) a case.",
)
async def delete_case(
    case_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user_from_request),
    service: InvestigationService = Depends(get_investigation_service),
) -> None:
    """Archive a case."""
    await service.delete_case(case_id, user, session)


@router.get(
    "/cases/{case_id}/export/csv",
    summary="Export case as CSV",
    description="Export case details and evidence as CSV file.",
)
async def export_case_csv(
    case_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user_from_request),
    service: InvestigationService = Depends(get_investigation_service),
):
    """Export case to CSV."""
    from fastapi.responses import StreamingResponse
    csv_content = await service.export_case_csv(case_id, user, session)
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=case_{case_id}.csv"},
    )


# =============================================================================
# Evidence Endpoints
# =============================================================================

@router.post(
    "/cases/{case_id}/evidence",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add evidence",
    description="Add evidence item to a case.",
)
async def add_evidence(
    case_id: int,
    payload: EvidenceCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user_from_request),
    service: InvestigationService = Depends(get_investigation_service),
) -> EvidenceResponse:
    """Add evidence to a case."""
    return await service.add_evidence(case_id, payload, user, session)


@router.post(
    "/cases/{case_id}/evidence/{evidence_id}/verify",
    response_model=EvidenceResponse,
    summary="Verify evidence",
    description="Mark evidence as verified.",
)
async def verify_evidence(
    case_id: int,
    evidence_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user_from_request),
    service: InvestigationService = Depends(get_investigation_service),
) -> EvidenceResponse:
    """Verify evidence item."""
    return await service.verify_evidence(case_id, evidence_id, user, session)


# =============================================================================
# Notes Endpoints
# =============================================================================

@router.post(
    "/cases/{case_id}/notes",
    response_model=CaseNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add case note",
    description="Add a note to a case. Internal notes visible only to investigators.",
)
async def add_note(
    case_id: int,
    payload: CaseNoteCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user_from_request),
    service: InvestigationService = Depends(get_investigation_service),
) -> CaseNoteResponse:
    """Add a note to a case."""
    return await service.add_note(case_id, payload, user, session)


# =============================================================================
# Stats Endpoint
# =============================================================================

@router.get(
    "/stats",
    response_model=InvestigationStats,
    summary="Investigation statistics",
    description="Get investigation dashboard statistics.",
)
async def get_stats(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user_from_request),
    service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationStats:
    """Get investigation statistics."""
    return await service.get_stats(user, session)


# =============================================================================
# Health Check
# =============================================================================

@router.get(
    "/health",
    summary="Investigation module health",
    description="Health check for the investigation module.",
)
async def health():
    """Module health check."""
    return {
        "status": "healthy",
        "module": "investigation",
        "version": "1.0.0",
    }

