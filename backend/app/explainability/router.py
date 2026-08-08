
"""
Explainability REST API Router
================================
"""


from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..core.config import APP_ENV
from ..core.db import get_session
from ..models import User
from .config import ExplainabilityConfig
from .schemas import ExplainabilityRequest, ExplainabilityResponse
from .service import get_explainability_service

router = APIRouter(
    prefix="/api/explain",
    tags=["explainability"],
    responses={
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error"},
    },
)


@router.post(
    "",
    response_model=ExplainabilityResponse,
    summary="Explain a Prediction",
    description="""
    Generate comprehensive explainability data for a model prediction.

    Returns:
    - Confidence score and risk level
    - Top contributing keywords
    - Human-readable explanation
    - Attention map (token-level importance)
    - Probability distribution graph
    - Feature importance breakdown
    - Counterfactual explanations (what changes would alter the prediction)
    - Prediction timeline (historical trends)
    - Model version info
    """,
)
async def explain_prediction(
    request: Request,
    payload: ExplainabilityRequest,
    session=Depends(get_session),
):
    """Generate comprehensive explainability for a prediction."""
    config = ExplainabilityConfig()
    if not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Explainability module is disabled",
        )

    service = get_explainability_service()

    # Extract user ID if authenticated
    user_id = None
    try:
        from ..core.security import decode_token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            payload_decoded = decode_token(token)
            if payload_decoded:
                from sqlmodel import select
                email = payload_decoded.get("sub")
                if email:
                    user = session.exec(select(User).where(User.email == email)).first()
                    if user:
                        user_id = user.id
    except Exception:
        pass

    result = await service.explain(payload, user_id=user_id)
    return result


@router.get(
    "/health",
    summary="Explainability Module Health",
    include_in_schema=APP_ENV != "production",
)
async def explainability_health():
    """Check explainability module health."""
    config = ExplainabilityConfig()
    return {
        "enabled": config.enabled,
        "model_version": config.model_version,
        "status": "healthy",
    }

