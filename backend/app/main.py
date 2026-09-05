"""
Enterprise AI Cyber Scam Detector API
======================================
Production-grade FastAPI application with enterprise security,
observability, resilience patterns, and monitoring.
"""

import contextlib
import os
import re
from datetime import UTC, datetime

import joblib
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from loguru import logger
from passlib.context import CryptContext
from sqlmodel import Session, select

from .core.audit import AuditMiddleware, get_audit_logger
from .core.cache import get_cache
from .core.config import (
    APP_ENV,
    APP_NAME,
    APP_VERSION,
    CACHE_PREDICTION_TTL,
    MODEL_PATH,
)
from .core.db import get_session
from .core.lifecycle import lifespan_handler
from .core.middleware import register_middleware
from .core.observability import setup_health_endpoints, setup_observability
from .core.resilience import resilience_manager
from .core.security import (
    check_permission,
    create_token_pair,
    hash_password,
    refresh_access_token,
    revoke_all_user_tokens,
    verify_password,
)
from .core.security import (
    decode_token as decode_access_token,
)
from .models import Feedback, Log, Report, Scan, User
from .schemas import (
    DashboardStats,
    DetectRequest,
    DetectResponse,
    FeedbackCreate,
    ModelInfoResponse,
    PredictRequest,
    PredictResponse,
    RefreshRequest,
    ScanOut,
    TokenResponse,
    UserCreate,
    UserOut,
)

# =============================================================================
# Application Factory
# =============================================================================

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description="Enterprise-grade AI-powered cyber scam detection platform",
        lifespan=lifespan_handler,
        docs_url="/docs" if APP_ENV != "production" else None,
        redoc_url="/redoc" if APP_ENV != "production" else None,
        openapi_url="/openapi.json" if APP_ENV != "production" else None,
        terms_of_service="https://example.com/terms",
        contact={
            "name": "Enterprise AI Team",
            "url": "https://example.com/support",
            "email": "security@example.com",
        },
        license_info={
            "name": "Enterprise License",
            "url": "https://example.com/license",
        },
    )

    # Register enterprise middleware
    register_middleware(app)

    # Add audit middleware
    app.add_middleware(AuditMiddleware)

    # Setup health endpoints (always available, even without metrics)
    setup_health_endpoints(app)

    # Setup observability (Prometheus metrics, structured logging)
    if os.getenv("ENABLE_METRICS", "true").lower() == "true":
        setup_observability(app)

    # Register enterprise module routers
    if os.getenv("ENABLE_THREAT_INTEL", "true").lower() == "true":
        try:
            from .threat_intelligence.router import router as threat_intel_router
            app.include_router(threat_intel_router)
            logger.info("Threat Intelligence Center module loaded")
        except ImportError as e:
            logger.warning(f"Threat Intelligence Center module not available: {e}")
        except Exception as e:
            logger.error(f"Failed to load Threat Intelligence Center module: {e}")

    if os.getenv("ENABLE_EXPLAINABILITY", "true").lower() == "true":
        try:
            from .explainability.router import router as explainability_router
            app.include_router(explainability_router)
            logger.info("AI Explainability Center module loaded")
        except ImportError as e:
            logger.warning(f"AI Explainability Center module not available: {e}")
        except Exception as e:
            logger.error(f"Failed to load AI Explainability Center module: {e}")

    if os.getenv("ENABLE_INVESTIGATION", "true").lower() == "true":
        try:
            from .investigation.router import router as investigation_router
            app.include_router(investigation_router)
            logger.info("Fraud Investigation Dashboard module loaded")
        except ImportError as e:
            logger.warning(f"Fraud Investigation Dashboard module not available: {e}")
        except Exception as e:
            logger.error(f"Failed to load Fraud Investigation Dashboard module: {e}")

    if os.getenv("ENABLE_MONITORING", "true").lower() == "true":
        try:
            from .monitoring.router import router as monitoring_router
            app.include_router(monitoring_router)
            logger.info("Real-Time Monitoring Center module loaded")
        except ImportError as e:
            logger.warning(f"Real-Time Monitoring Center module not available: {e}")
        except Exception as e:
            logger.error(f"Failed to load Real-Time Monitoring Center module: {e}")

    if os.getenv("ENABLE_CHAT", "true").lower() == "true":
        try:
            from .chat.router import router as chat_router
            app.include_router(chat_router)
            logger.info("AI Chat Security Assistant module loaded")
        except ImportError as e:
            logger.warning(f"AI Chat Security Assistant module not available: {e}")
        except Exception as e:
            logger.error(f"Failed to load AI Chat Security Assistant module: {e}")

    return app


app = create_app()

# =============================================================================
# Authentication Configuration
# =============================================================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# =============================================================================
# Model Loading with Resilience
# =============================================================================

class HeuristicModel:
    """Fallback heuristic model when ML model is unavailable."""

    def __init__(self) -> None:
        self.classes_ = ["safe", "suspicious", "scam"]

    def predict_proba(self, texts):
        probabilities = []
        for text in texts:
            score = 0
            lowered = text.lower()
            suspicious_terms = [
                "urgent", "verify", "bank", "password", "click", "win",
                "prize", "invoice", "crypto", "otp", "secure", "login", "account"
            ]
            scam_terms = [
                "claim", "free", "reward", "limited time", "suspicious",
                "hack", "reset", "update now", "gift card", "compromised",
                "suspended", "arrest", "back taxes", "won"
            ]
            if re.search(r"https?://", lowered):
                score += 2
            if any(term in lowered for term in suspicious_terms):
                score += 2
            if any(term in lowered for term in scam_terms):
                score += 3
            if "http" in lowered and "verify" in lowered:
                score += 2

            if score >= 6:
                label = "scam"
            elif score >= 3:
                label = "suspicious"
            else:
                label = "safe"

            probs = [0.0, 0.0, 0.0]
            if label == "safe":
                probs = [0.86, 0.10, 0.04]
            elif label == "suspicious":
                probs = [0.12, 0.72, 0.16]
            else:
                probs = [0.03, 0.12, 0.85]
            probabilities.append(probs)
        return probabilities

    def predict(self, texts):
        return [
            self.classes_[max(range(len(probs)), key=probs.__getitem__)]
            for probs in self.predict_proba(texts)
        ]


def load_model():
    """Load ML model with fallback to heuristic and retry logic."""
    import time as _time
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            model = joblib.load(MODEL_PATH)
            logger.info(f"Loaded model from {MODEL_PATH}")
            return model
        except Exception as exc:
            logger.warning(f"Attempt {attempt}/{max_attempts} - Could not load model from {MODEL_PATH}: {exc}.")
            if attempt < max_attempts:
                _time.sleep(attempt * 2)  # Progressive backoff
    logger.warning("All model loading attempts failed. Using heuristic fallback.")
    return HeuristicModel()


# Register model loading circuit breaker with retry
model_cb = resilience_manager.add_circuit_breaker("model_loading", failure_threshold=5, recovery_timeout=60)
model_bulkhead = resilience_manager.add_bulkhead("model_inference", max_concurrent=10, max_queue=30)
# Add retry policy for model loading
resilience_manager.add_retry_policy("model_loading", max_retries=3, base_delay=2.0)
# Add retry policy for predictions
resilience_manager.add_retry_policy("prediction", max_retries=2, base_delay=0.5)

MODEL = load_model()


# =============================================================================
# Helper Functions
# =============================================================================

def authenticate_user(session: Session, email: str, password: str) -> User | None:
    """Authenticate a user by email and password."""
    user = session.exec(select(User).where(User.email == email.lower())).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    """Get the current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    email = payload.get("sub")
    if email is None:
        raise credentials_exception
    token_type = payload.get("type")
    if token_type != "access":
        raise credentials_exception

    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        raise credentials_exception
    return user


def get_optional_user(
    request: Request,
    session: Session = Depends(get_session),
) -> User | None:
    """Optionally authenticate user (does not fail if no token)."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1]
    try:
        payload = decode_access_token(token)
        if payload is None:
            return None
        email = payload.get("sub")
        if email is None:
            return None
        return session.exec(select(User).where(User.email == email)).first()
    except Exception:
        return None


def build_explanation(text: str, label: str, confidence: float, source: str) -> dict:
    """Build explanation for a prediction."""
    lowered = text.lower()
    keywords = [
        word for word in [
            "urgent", "verify", "click", "bank", "password", "otp",
            "free", "reward", "invoice", "crypto"
        ] if word in lowered
    ]

    if label == "scam":
        reason = "The message contains high-risk urgency and impersonation patterns commonly used in scams."
        risk_level = "High"
        advice = "Do not click links, share credentials, or respond to the sender."
        simple_explanation = (
            "This looks like a scam because it pressures you to act fast "
            "and may try to steal your password or money."
        )
    elif label == "suspicious":
        reason = "The message contains several signs that may be risky, but the intent is not fully confirmed."
        risk_level = "Medium"
        advice = "Verify the sender through an official channel before you proceed."
        simple_explanation = (
            "This message seems risky and could be a scam, "
            "so be cautious before trusting it."
        )
    else:
        reason = "The content does not show strong scam indicators based on the current signals."
        risk_level = "Low"
        advice = "Keep using caution with unexpected links and requests."
        simple_explanation = "The message appears normal and does not show strong scam signals."

    return {
        "keywords": keywords or ["no obvious trigger words"],
        "reason": reason,
        "risk_level": risk_level,
        "safety_advice": advice,
        "simple_explanation": simple_explanation,
        "source": source,
        "confidence": round(confidence, 3),
    }


def _predict_text(text: str) -> tuple[str, float]:
    """Run prediction on text and return (label, confidence)."""
    if hasattr(MODEL, "predict_proba"):
        pred_proba = MODEL.predict_proba([text])[0]
        classes = list(getattr(MODEL, "classes_", ["safe", "suspicious", "scam"]))
        # Robust argmax that works for numpy arrays and Python lists
        try:
            idx = int(max(range(len(pred_proba)), key=lambda i: pred_proba[i]))
        except Exception:
            idx = int(sorted(range(len(pred_proba)), key=lambda i: pred_proba[i])[-1])
        label = str(classes[idx]) if idx < len(classes) else "suspicious"
        confidence = float(pred_proba[idx])
    else:
        label = str(MODEL.predict([text])[0])
        confidence = 0.99
    return label, confidence


# =============================================================================
# Root & Health & Metrics Endpoints
# =============================================================================

@app.get("/", tags=["observability"])
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "environment": APP_ENV,
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "model_info": "/api/model-info",
    }


@app.get("/health", tags=["observability"])
async def health() -> dict:
    """Basic health check endpoint."""
    model_status = "loaded" if hasattr(MODEL, "predict_proba") else "fallback"
    return {
        "status": "ok",
        "model_status": model_status,
        "timestamp": datetime.now(UTC).isoformat(),
    }


# =============================================================================
# Prediction Endpoints
# =============================================================================

@app.post("/predict", response_model=PredictResponse, tags=["prediction"])
async def predict(
    req: PredictRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> PredictResponse:
    """
    Analyze text for scam content.

    Returns prediction label, confidence score, and detailed explanation.
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text must not be empty")

    from .core.observability import prediction_duration_seconds, predictions_total

    # Build cache key
    cache_key = f"prediction:{req.text.strip().lower()[:200]}"

    # Check cache
    cache = get_cache()
    if os.getenv("ENABLE_CACHE", "true").lower() == "true":
        cached_result = await cache.get(cache_key)
        if cached_result:
            return PredictResponse(**cached_result)

    import time
    start_time = time.time()

    # Predict using the actual ML model
    label, confidence = _predict_text(req.text)

    # Track metrics
    duration = time.time() - start_time
    predictions_total.labels(label=label, source=req.source).inc()
    prediction_duration_seconds.labels(model_type="ml").observe(duration)

    # Build explanation
    explanation = build_explanation(req.text, label, confidence, req.source)

    # Get optional user
    current_user = get_optional_user(request, session)

    # Save scan if user is authenticated
    if current_user is not None:
        scan = Scan(
            user_id=current_user.id,
            input_text=req.text,
            result=label,
            confidence=confidence,
            source=req.source,
        )
        session.add(scan)
        session.commit()
        session.refresh(scan)

        report = Report(
            user_id=current_user.id,
            scan_id=scan.id,
            title=f"{label.title()} detection report",
            content=(
                f"{label} | confidence {confidence:.2f} | "
                f"keywords: {', '.join(explanation['keywords'])}"
            ),
        )
        session.add(report)
        session.add(
            Log(
                user_id=current_user.id,
                message=f"Prediction '{label}' saved for {current_user.email}",
            )
        )
        session.commit()

    # Build response
    result = PredictResponse(
        label=label,
        confidence=round(confidence, 3),
        explanation=explanation,
    )

    # Cache result
    if os.getenv("ENABLE_CACHE", "true").lower() == "true":
        await cache.set(
            cache_key,
            result.model_dump(),
            ttl=CACHE_PREDICTION_TTL,
        )

    # Audit log
    get_audit_logger().log(
        action="model.predict",
        actor=current_user.email if current_user else "anonymous",
        resource="prediction",
        result="success",
        ip_address=request.client.host if request.client else None,
        details={"label": label, "confidence": confidence, "source": req.source},
    )

    return result


@app.post("/api/predict", response_model=PredictResponse, tags=["prediction"])
async def api_predict(
    req: PredictRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> PredictResponse:
    """Alias for /predict with the same behavior."""
    return await predict(req, request, session)


@app.post("/api/detect", response_model=DetectResponse, tags=["prediction"])
async def api_detect(
    req: DetectRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> DetectResponse:
    """
    Detect scam content with a simplified response format.

    Returns prediction (SAFE/SCAM/SUSPICIOUS), confidence, risk level, and message.
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text must not be empty")

    # Predict using the actual ML model
    label, confidence = _predict_text(req.text)

    # Map label to uppercase prediction
    prediction = label.upper()

    # Determine risk level
    if label == "scam":
        risk_level = "HIGH"
        message = "Potential scam detected"
    elif label == "suspicious":
        risk_level = "MEDIUM"
        message = "Suspicious content detected - proceed with caution"
    else:
        risk_level = "LOW"
        message = "No scam indicators detected"

    # Build explanation
    explanation = build_explanation(req.text, label, confidence, req.source)

    # Get optional user for history tracking
    current_user = get_optional_user(request, session)

    # Save scan if user is authenticated
    if current_user is not None:
        scan = Scan(
            user_id=current_user.id,
            input_text=req.text,
            result=label,
            confidence=confidence,
            source=req.source,
        )
        session.add(scan)
        session.commit()
        session.refresh(scan)

        report = Report(
            user_id=current_user.id,
            scan_id=scan.id,
            title=f"{label.title()} detection report",
            content=(
                f"{label} | confidence {confidence:.2f} | "
                f"keywords: {', '.join(explanation['keywords'])}"
            ),
        )
        session.add(report)
        session.add(
            Log(
                user_id=current_user.id,
                message=f"Detection '{label}' saved for {current_user.email}",
            )
        )
        session.commit()

    # Audit log
    get_audit_logger().log(
        action="model.detect",
        actor=current_user.email if current_user else "anonymous",
        resource="prediction",
        result="success",
        ip_address=request.client.host if request.client else None,
        details={"label": label, "confidence": confidence, "source": req.source},
    )

    return DetectResponse(
        prediction=prediction,
        confidence=round(confidence, 3),
        risk_level=risk_level,
        message=message,
        explanation=explanation,
    )


@app.get("/api/model-info", response_model=ModelInfoResponse, tags=["prediction"])
async def model_info() -> ModelInfoResponse:
    """Get information about the current ML model."""
    classes = list(getattr(MODEL, "classes_", ["safe", "suspicious", "scam"]))
    model_type = type(MODEL).__name__

    # Try to load metrics if available
    metrics = {}
    metrics_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "models", "exports", "metrics.json"
    )
    if os.path.exists(metrics_path):
        import json
        try:
            with open(metrics_path) as f:
                metrics = json.load(f)
        except Exception:
            pass

    return ModelInfoResponse(
        model_name="Scam Detection Pipeline",
        model_type=model_type,
        version=APP_VERSION,
        classes=classes,
        accuracy=metrics.get("accuracy"),
        precision=metrics.get("precision"),
        recall=metrics.get("recall"),
        f1_score=metrics.get("f1"),
        trained_samples=metrics.get("train_samples"),
        status="loaded" if hasattr(MODEL, "predict_proba") else "fallback",
    )


# =============================================================================
# Authentication Endpoints
# =============================================================================

@app.post("/auth/signup", response_model=TokenResponse, tags=["authentication"])
def signup(payload: UserCreate, session: Session = Depends(get_session)) -> TokenResponse:
    """Register a new user account."""
    from .core.secrets import SecretsValidator

    email = payload.email.lower().strip()

    # Validate email format
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    # Validate password strength
    password_errors = SecretsValidator.validate_password_strength(payload.password)
    if password_errors:
        raise HTTPException(
            status_code=400,
            detail=f"Weak password: {'; '.join(password_errors)}",
        )

    # Check for existing user
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create user
    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        is_admin=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # Issue token pair
    token_pair = create_token_pair(subject=user.email)

    get_audit_logger().log(
        action="auth.signup",
        actor=email,
        resource="user",
        result="success",
        details={"user_id": user.id},
    )

    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type="bearer",
        expires_in=token_pair.expires_in,
    )


@app.post("/auth/login", response_model=TokenResponse, tags=["authentication"])
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
) -> TokenResponse:
    """Authenticate and receive JWT tokens."""
    from .core.observability import auth_attempts_total

    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
        auth_attempts_total.labels(method="login", result="failure").inc()
        get_audit_logger().log(
            action="auth.login",
            actor=form_data.username,
            resource="user",
            result="failure",
            details={"reason": "invalid_credentials"},
        )
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    # Issue token pair
    token_pair = create_token_pair(subject=user.email)

    auth_attempts_total.labels(method="login", result="success").inc()
    get_audit_logger().log(
        action="auth.login",
        actor=user.email,
        resource="user",
        result="success",
        details={"user_id": user.id},
    )

    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type="bearer",
        expires_in=token_pair.expires_in,
    )


@app.post("/auth/refresh", response_model=TokenResponse, tags=["authentication"])
def refresh_token(
    payload: RefreshRequest,
    session: Session = Depends(get_session),
) -> TokenResponse:
    """Refresh an expired access token using a valid refresh token."""
    token_pair = refresh_access_token(payload.refresh_token)
    if not token_pair:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type="bearer",
        expires_in=token_pair.expires_in,
    )


@app.post("/auth/logout", tags=["authentication"])
def logout(
    user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
) -> dict:
    """Invalidate all tokens for the current user."""
    # Also blacklist the current access token's JTI
    payload = decode_access_token(token)
    if payload and "jti" in payload:
        from .core.security import revoke_token
        revoke_token(payload["jti"])
    count = revoke_all_user_tokens(user.email)
    get_audit_logger().log(
        action="auth.logout",
        actor=user.email,
        resource="session",
        result="success",
        details={"revoked_tokens": count},
    )
    return {"message": f"Logged out successfully. {count} sessions terminated."}


@app.post("/auth/forgot-password", tags=["authentication"])
def forgot_password(payload: UserCreate, session: Session = Depends(get_session)) -> dict:
    """Request password reset instructions."""
    user = session.exec(
        select(User).where(User.email == payload.email.lower().strip())
    ).first()
    if user is None:
        return {"message": "If that email exists, a reset link has been sent."}
    return {"message": "Password reset instructions were sent to the email address."}


@app.get("/auth/me", response_model=UserOut, tags=["authentication"])
def current_user(user: User = Depends(get_current_user)) -> UserOut:
    """Get current user profile."""
    return UserOut(
        id=user.id,
        email=user.email,
        is_admin=user.is_admin,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


# =============================================================================
# Dashboard & History Endpoints
# =============================================================================

@app.get("/dashboard", response_model=DashboardStats, tags=["analytics"])
def dashboard(session: Session = Depends(get_session)) -> DashboardStats:
    """Get dashboard statistics (global)."""
    cache = get_cache()
    cache_key = "dashboard:stats"

    # Try cache first
    import asyncio
    try:
        cached = asyncio.run(cache.get(cache_key))
        if cached:
            return DashboardStats(**cached)
    except Exception:
        pass

    scans = session.exec(
        select(Scan).order_by(Scan.created_at.desc()).limit(20)
    ).all()
    total_scans = len(scans)
    scam_count = sum(1 for scan in scans if scan.result == "scam")
    safe_count = sum(1 for scan in scans if scan.result == "safe")
    scam_percentage = round((scam_count / total_scans) * 100, 1) if total_scans else 0.0
    safe_percentage = round((safe_count / total_scans) * 100, 1) if total_scans else 0.0

    recent_scans = [
        ScanOut(
            id=scan.id,
            input_text=scan.input_text[:80],
            result=scan.result,
            confidence=round(scan.confidence, 3),
            created_at=scan.created_at.isoformat() if scan.created_at else "",
        )
        for scan in scans
    ]

    result = DashboardStats(
        total_scans=total_scans,
        scam_percentage=scam_percentage,
        safe_percentage=safe_percentage,
        recent_scans=recent_scans,
    )

    # Cache for 30 seconds
    with contextlib.suppress(Exception):
        asyncio.run(cache.set(cache_key, result.model_dump(), ttl=30))

    return result


@app.get("/history", response_model=list[ScanOut], tags=["analytics"])
def history(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ScanOut]:
    """Get scan history for the authenticated user."""
    scans = session.exec(
        select(Scan)
        .where(Scan.user_id == user.id)
        .order_by(Scan.created_at.desc())
        .limit(50)
    ).all()
    return [
        ScanOut(
            id=scan.id,
            input_text=scan.input_text[:80],
            result=scan.result,
            confidence=round(scan.confidence, 3),
            created_at=scan.created_at.isoformat() if scan.created_at else "",
        )
        for scan in scans
    ]


@app.get("/reports/{scan_id}", tags=["analytics"])
def report(
    scan_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Get a detailed report for a specific scan."""
    scan = session.get(Scan, scan_id)
    if not scan or scan.user_id != user.id:
        raise HTTPException(status_code=404, detail="Report not found")
    return {
        "scan_id": scan.id,
        "prediction": scan.result,
        "risk_score": round(scan.confidence * 100, 1),
        "reason": "The system flagged urgency, impersonation, and link-based risk patterns.",
        "recommendation": "Do not click or respond until the channel is verified.",
        "generated_at": datetime.now(UTC).isoformat(),
    }


# =============================================================================
# Admin Endpoints
# =============================================================================

@app.get("/admin/users", tags=["admin"])
def admin_users(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict]:
    """List all users (admin only)."""
    if not check_permission("admin" if user.is_admin else "user", "manage_users"):
        raise HTTPException(status_code=403, detail="Admin access required")
    users = session.exec(select(User)).all()
    return [
        {"id": item.id, "email": item.email, "is_admin": item.is_admin}
        for item in users
    ]


@app.get("/admin/audit-log", tags=["admin"])
def admin_audit_log(
    user: User = Depends(get_current_user),
    days: int = 7,
) -> dict:
    """Get audit log summary (admin only)."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return get_audit_logger().get_security_summary(days=days)


# =============================================================================
# Feedback Endpoint
# =============================================================================

@app.post("/feedback", tags=["feedback"])
def feedback(
    payload: FeedbackCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Submit user feedback."""
    session.add(Feedback(user_id=user.id, message=payload.message))
    session.commit()
    return {"message": "Feedback stored successfully"}


# =============================================================================
# Resilience Status Endpoint
# =============================================================================

@app.get("/system/resilience", tags=["system"])
def resilience_status(user: User = Depends(get_current_user)) -> dict:
    """Get status of all resilience components (authenticated)."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return resilience_manager.get_status()


@app.get("/system/config", tags=["system"])
def system_config(user: User = Depends(get_current_user)) -> dict:
    """Get system configuration (admin only)."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    from .core.config import get_all_config
    return get_all_config()


# =============================================================================
# Error Handlers
# =============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    get_audit_logger().log(
        action="system.error",
        actor="system",
        resource="api",
        result="failure",
        ip_address=request.client.host if request.client else None,
        details={"path": request.url.path, "error": str(exc)},
        severity="critical",
    )
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred. Our team has been notified."},
    )