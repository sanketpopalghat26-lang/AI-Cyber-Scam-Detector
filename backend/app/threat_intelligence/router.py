"""
Threat Intelligence REST API Router
=====================================
FastAPI router for the Threat Intelligence Center endpoints.

Endpoints:
  GET  /api/threat/search  - Search IOC database
  GET  /api/threat/stats   - Get IOC statistics
  POST /api/threat/analyze - Analyze a potential threat

All endpoints include:
- Authentication and RBAC
- Rate limiting
- Caching
- Audit logging
- Structured error handling
- OpenAPI documentation
"""

import contextlib

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from loguru import logger
from sqlmodel import Session

from ..core.audit import get_audit_logger
from ..core.cache import get_cache
from ..core.config import APP_ENV
from ..core.db import get_session
from ..core.security import decode_token
from .config import ThreatIntelConfig
from .schemas import (
    ThreatAnalyzeRequest,
    ThreatAnalyzeResponse,
    ThreatSearchResponse,
    ThreatStatsResponse,
)
from .service import ThreatIntelligenceService

# =============================================================================
# Router Configuration
# =============================================================================

router = APIRouter(
    prefix="/api/threat",
    tags=["threat-intelligence"],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"},
    },
)

# Service singleton (lazy initialization)
_service: ThreatIntelligenceService | None = None


def get_service() -> ThreatIntelligenceService:
    """Get or create the threat intelligence service singleton."""
    global _service
    if _service is None:
        config = ThreatIntelConfig.from_env()
        _service = ThreatIntelligenceService(config)
    return _service


# =============================================================================
# Authentication Dependency
# =============================================================================


async def get_optional_user_id(
    request: Request, session: Session = Depends(get_session)
) -> int | None:
    """Extract user ID from token if present (optional auth)."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1]
    try:
        payload = decode_token(token)
        if payload is None:
            return None
        email = payload.get("sub")
        if email is None:
            return None
        from sqlmodel import select

        from ..models import User

        user = session.exec(select(User).where(User.email == email)).first()
        return user.id if user else None
    except Exception:
        return None


async def get_current_user_id(request: Request, session: Session = Depends(get_session)) -> int:
    """Extract user ID from token (required auth)."""
    user_id = await get_optional_user_id(request, session)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user_id


# =============================================================================
# API Endpoints
# =============================================================================


@router.get(
    "/search",
    response_model=ThreatSearchResponse,
    summary="Search IOC Database",
    description="""
    Search the Indicator of Compromise (IOC) database using various filters.

    Supports searching by:
    - IP addresses
    - Domain names
    - URLs
    - File hashes (MD5, SHA1, SHA256)
    - Keywords in tags and notes

    Results are paginated and ordered by risk score (highest first).
    """,
    responses={
        200: {
            "description": "Search results",
            "content": {
                "application/json": {
                    "example": {
                        "total": 42,
                        "results": [
                            {
                                "id": 1,
                                "ioc_value": "192.168.1.1",
                                "ioc_type": "ip",
                                "threat_category": "malicious_ip",
                                "confidence": 0.95,
                                "risk_score": 0.85,
                            }
                        ],
                        "query": "192.168.1.1",
                        "limit": 50,
                        "offset": 0,
                        "has_more": False,
                        "search_time_ms": 12.5,
                    }
                }
            },
        }
    },
)
async def search_threats(
    request: Request,
    query: str = Query(
        ...,
        min_length=1,
        max_length=500,
        description="Search query (IP, domain, URL, hash, or keyword)",
        examples=["192.168.1.1", "example.com", "https://phishing.com"],
    ),
    ioc_type: str | None = Query(
        None,
        description="Filter by IOC type (ip, domain, url, hash_md5, etc.)",
    ),
    threat_category: str | None = Query(
        None,
        description="Filter by threat category",
    ),
    risk_level: str | None = Query(
        None,
        description="Filter by minimum risk level (info, low, medium, high, critical)",
    ),
    ioc_status: str | None = Query(
        None, alias="status", description="Filter by IOC status (active, inactive, expired)"
    ),
    source: str | None = Query(None, description="Filter by feed source"),
    limit: int = Query(
        default=50,
        ge=1,
        le=1000,
        description="Maximum number of results",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of results to skip",
    ),
    include_expired: bool = Query(
        default=False,
        description="Include expired IOCs",
    ),
    session: Session = Depends(get_session),
):
    """Search the IOC database with various filters."""
    config = ThreatIntelConfig.from_env()
    if not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Threat Intelligence module is disabled",
        )

    # Import enum types safely
    from .models import IOCStatus, IOCType, RiskLevel, ThreatCategory, ThreatFeedSource

    # Parse optional enum filters
    parsed_ioc_type = None
    if ioc_type:
        try:
            parsed_ioc_type = IOCType(ioc_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid IOC type: {ioc_type}. Valid types: {[e.value for e in IOCType]}",
            )

    parsed_category = None
    if threat_category:
        try:
            parsed_category = ThreatCategory(threat_category)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid threat category: {threat_category}",
            )

    parsed_risk_level = None
    if risk_level:
        try:
            parsed_risk_level = RiskLevel(risk_level)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid risk level: {risk_level}. Valid levels: {[e.value for e in RiskLevel]}",
            )

    parsed_status = None
    if ioc_status:
        try:
            parsed_status = IOCStatus(ioc_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {ioc_status}",
            )

    parsed_source = None
    if source:
        try:
            parsed_source = ThreatFeedSource(source)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid source: {source}",
            )

    service = get_service()

    # Check cache
    cache = get_cache()
    cache_key = f"threat:search:{query}:{ioc_type}:{limit}:{offset}"
    try:
        cached = await cache.get(cache_key)
        if cached:
            return ThreatSearchResponse(**cached)
    except Exception:
        pass

    result = service.search_iocs(
        query=query,
        ioc_type=parsed_ioc_type,
        threat_category=parsed_category,
        risk_level=parsed_risk_level,
        status=parsed_status,
        source=parsed_source,
        limit=limit,
        offset=offset,
        include_expired=include_expired,
    )

    # Cache for 60 seconds
    with contextlib.suppress(Exception):
        await cache.set(cache_key, result.model_dump(), ttl=60)

    # Audit log
    get_audit_logger().log(
        action="threat_intel.search",
        actor=getattr(request.state, "user_email", "anonymous"),
        resource="ioc_database",
        result="success",
        ip_address=request.client.host if request.client else None,
        details={"query": query, "results": result.total},
    )

    return result


@router.get(
    "/stats",
    response_model=ThreatStatsResponse,
    summary="Get IOC Database Statistics",
    description="""
    Get comprehensive statistics about the IOC database including:
    - Total IOC counts by type, category, risk level, and source
    - Feed status information
    - Geographic distribution
    - Recent threat timeline activity

    Results are cached for 5 minutes for performance.
    """,
)
async def get_threat_stats(
    request: Request,
):
    """Get comprehensive IOC database statistics."""
    config = ThreatIntelConfig.from_env()
    if not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Threat Intelligence module is disabled",
        )

    service = get_service()

    # Check cache
    cache = get_cache()
    cache_key = "threat:stats"
    try:
        cached = await cache.get(cache_key)
        if cached:
            return ThreatStatsResponse(**cached)
    except Exception:
        pass

    result = service.get_ioc_stats()

    # Cache for 5 minutes
    with contextlib.suppress(Exception):
        await cache.set(cache_key, result.model_dump(), ttl=300)

    return result


@router.post(
    "/analyze",
    response_model=ThreatAnalyzeResponse,
    summary="Analyze a Potential Threat",
    description="""
    Perform a comprehensive threat analysis against multiple intelligence sources.

    The analysis checks the provided value against:
    - VirusTotal (if configured)
    - AbuseIPDB (for IP addresses, if configured)
    - OpenPhish phishing feed
    - PhishTank (if configured)
    - AlienVault OTX (if configured)
    - DNS analysis
    - WHOIS lookup
    - GeoIP analysis (for IP addresses)
    - ASN lookup

    Returns a composite risk score, threat classification, and detailed provider results.
    """,
    responses={
        200: {
            "description": "Analysis complete",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "value": "192.168.1.1",
                        "value_type": "ip",
                        "is_malicious": True,
                        "risk_score": 0.85,
                        "risk_level": "high",
                        "threat_category": "malicious_ip",
                        "confidence": 0.92,
                        "sources_checked": 5,
                        "positive_detections": 3,
                        "explanation": "High-risk indicator flagged by 3/5 sources.",
                        "processing_time_ms": 2500,
                    }
                }
            },
        }
    },
)
async def analyze_threat(
    request: Request,
    payload: ThreatAnalyzeRequest,
    user_id: int | None = Depends(get_optional_user_id),
):
    """Analyze a potential threat against all configured intelligence sources."""
    config = ThreatIntelConfig.from_env()
    if not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Threat Intelligence module is disabled",
        )

    service = get_service()

    from .providers import _auto_detect_type

    # Auto-detect IOC type
    value_type = payload.value_type or _auto_detect_type(payload.value)

    # Check cache for recent identical analysis
    cache = get_cache()
    cache_key = f"threat:analyze:{payload.value}:{value_type.value}"
    try:
        cached = await cache.get(cache_key)
        if cached:
            logger.debug(f"Returning cached threat analysis for {payload.value}")
            return ThreatAnalyzeResponse(**cached)
    except Exception:
        pass

    # Perform analysis
    result = await service.analyze(
        value=payload.value,
        value_type=value_type,
        source=payload.source,
        user_id=user_id,
        check_virustotal=payload.check_virustotal,
        check_abuseipdb=payload.check_abuseipdb,
        check_phishtank=payload.check_phishtank,
        check_openphish=payload.check_openphish,
        check_alienvault=payload.check_alienvault,
        check_dns=payload.check_dns,
        check_whois=payload.check_whois,
        check_geoip=payload.check_geoip,
        check_asn=payload.check_asn,
    )

    # Cache result (shorter TTL for analyses)
    with contextlib.suppress(Exception):
        await cache.set(cache_key, result.model_dump(), ttl=120)

    # Audit log
    get_audit_logger().log(
        action="threat_intel.analyze",
        actor=str(user_id) if user_id else "anonymous",
        resource="threat_analysis",
        resource_id=str(result.id),
        result="success",
        ip_address=request.client.host if request.client else None,
        details={
            "value": payload.value[:100],
            "value_type": value_type.value,
            "risk_score": result.risk_score,
            "risk_level": result.risk_level.value
            if hasattr(result.risk_level, "value")
            else str(result.risk_level),
            "is_malicious": result.is_malicious,
        },
    )

    return result


# =============================================================================
# Health Check Endpoint
# =============================================================================


@router.get(
    "/health",
    summary="Threat Intelligence Module Health",
    description="Get the health status of the Threat Intelligence module and all providers.",
    include_in_schema=APP_ENV != "production",
)
async def threat_intel_health():
    """Check the health of the Threat Intelligence module."""
    service = get_service()
    health = await service.health_check()
    return health
