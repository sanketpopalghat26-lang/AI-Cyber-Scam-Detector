"""
AI Chat Security Assistant Router
===================================
FastAPI router exposing the RAG-based chat assistant endpoints.

Endpoints:
  POST /api/chat - Send a message to the assistant
  POST /api/chat/sessions - Create a new chat session
  GET  /api/chat/sessions - List chat sessions
  GET  /api/chat/sessions/{id}/messages - Get message history
  POST /api/chat/detect-intent - Detect the intent of a query
  GET  /api/chat/health - Module health check
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
from .config import ChatConfig
from .models import ChatMessage, ChatSession
from .schemas import (
    ChatHistoryResponse,
    ChatIntentResponse,
    ChatMessageOut,
    ChatRequest,
    ChatResponse,
    ChatSessionCreate,
    ChatSessionOut,
)
from .service import ChatAssistantService

router = APIRouter(
    prefix="/api/chat",
    tags=["ai-chat-assistant"],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"},
    },
)

_service: ChatAssistantService | None = None


def get_service() -> ChatAssistantService:
    """Get or create the chat service singleton."""
    global _service
    if _service is None:
        _service = ChatAssistantService(ChatConfig.from_env())
    return _service


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


def _to_message_out(msg: ChatMessage) -> ChatMessageOut:
    """Convert a ChatMessage model to its response schema."""
    return ChatMessageOut(
        id=msg.id,
        session_id=msg.session_id,
        role=msg.role,
        content=msg.content,
        intent=msg.intent,
        retrieved_context=msg.retrieved_context,
        confidence=msg.confidence,
        model=msg.model,
        created_at=msg.created_at.isoformat() if msg.created_at else "",
    )


def _to_session_out(s: ChatSession) -> ChatSessionOut:
    """Convert a ChatSession model to its response schema."""
    return ChatSessionOut(
        id=s.id,
        user_id=s.user_id,
        title=s.title,
        is_active=s.is_active,
        created_at=s.created_at.isoformat() if s.created_at else "",
        updated_at=s.updated_at.isoformat() if s.updated_at else None,
    )


@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a message to the AI Security Assistant",
    description="""
    Send a natural-language query to the AI Security Assistant.

    The assistant uses Retrieval-Augmented Generation (RAG) over the
    platform's scans, predictions, reports, threat intelligence, and
    investigations to provide grounded, explainable answers.

    Examples:
      - "Why is this scam?"
      - "Explain this URL"
      - "Generate investigation report"
      - "Show today's attacks"
      - "Compare two predictions"
    """,
    responses={
        200: {
            "description": "Assistant response",
            "content": {
                "application/json": {
                    "example": {
                        "session_id": 1,
                        "intent": "explain_prediction",
                        "response": "Here's why the content was classified as a scam...",
                        "sources": [],
                        "confidence": 0.8,
                        "model": "internal-rag",
                        "processing_time_ms": 45.2,
                        "suggestions": [],
                    }
                }
            },
        }
    },
)
async def chat(
    request: Request,
    payload: ChatRequest,
    user_id: int | None = Depends(get_optional_user_id),
    session: Session = Depends(get_session),
):
    """Process a chat message."""
    config = ChatConfig.from_env()
    if not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Chat module is disabled",
        )

    service = get_service()

    # Check cache for identical recent query (idempotency)
    cache = get_cache()
    cache_key = f"chat:recent:{payload.message.strip().lower()[:100]}"
    try:
        cached = await cache.get(cache_key)
        if cached and payload.session_id is None:
            return ChatResponse(**{**cached, "session_id": cached["session_id"]})
    except Exception:
        pass

    try:
        result = await service.chat(
            session=session,
            user_id=user_id,
            message=payload.message,
            session_id=payload.session_id,
            source=payload.source or "chat",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Chat processing failed: {e}")
        get_audit_logger().log(
            action="chat.error",
            actor=str(user_id) if user_id else "anonymous",
            resource="chat",
            result="failure",
            details={"error": str(e)},
            severity="warning",
        )
        raise HTTPException(
            status_code=500, detail="Failed to process chat message"
        )

    # Cache the result briefly for identical queries
    with contextlib.suppress(Exception):
        await cache.set(
            cache_key, result, ttl=30
        )

    return ChatResponse(
        message=result["message"],
        session_id=result["session_id"],
        intent=result["intent"],
        response=result["response"],
        sources=result["sources"],
        confidence=result["confidence"],
        model=result["model"],
        processing_time_ms=result["processing_time_ms"],
        suggestions=result.get("suggestions", []),
    )


@router.post(
    "/sessions",
    response_model=ChatSessionOut,
    summary="Create a new chat session",
)
async def create_session(
    payload: ChatSessionCreate,
    user_id: int | None = Depends(get_optional_user_id),
    session: Session = Depends(get_session),
):
    """Create a new chat session."""
    chat_session = ChatSession(
        user_id=user_id,
        title=payload.title or "New Chat",
    )
    session.add(chat_session)
    session.commit()
    session.refresh(chat_session)
    return _to_session_out(chat_session)


@router.get(
    "/sessions",
    response_model=list[ChatSessionOut],
    summary="List chat sessions",
)
async def list_sessions(
    user_id: int | None = Depends(get_optional_user_id),
    session: Session = Depends(get_session),
    limit: int = Query(default=20, ge=1, le=100),
):
    """List chat sessions for the current user."""
    service = get_service()
    sessions = service.list_sessions(session, user_id, limit=limit)
    return [_to_session_out(s) for s in sessions]


@router.get(
    "/sessions/{session_id}/messages",
    response_model=ChatHistoryResponse,
    summary="Get message history for a session",
)
async def get_history(
    session_id: int,
    user_id: int | None = Depends(get_optional_user_id),
    session: Session = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Get the full message history for a chat session."""
    chat_session = session.get(ChatSession, session_id)
    if chat_session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    if user_id and chat_session.user_id and chat_session.user_id != user_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to view this session"
        )

    service = get_service()
    messages = service.get_session_messages(session, session_id, limit=limit)
    return ChatHistoryResponse(
        session=_to_session_out(chat_session),
        messages=[_to_message_out(m) for m in messages],
        total=len(messages),
    )


@router.post(
    "/detect-intent",
    response_model=ChatIntentResponse,
    summary="Detect the intent of a query",
    description="Detect which intent a natural-language query maps to.",
)
async def detect_intent(payload: ChatRequest):
    """Detect the intent of a user query."""
    service = get_service()
    intent, confidence, keywords = service.detect_intent(payload.message)
    return ChatIntentResponse(
        message=payload.message,
        intent=intent,
        confidence=round(confidence, 3),
        matched_keywords=keywords,
    )


@router.get(
    "/health",
    summary="Chat Module Health",
    description="Get the health status of the AI Chat module.",
    include_in_schema=APP_ENV != "production",
)
async def chat_health():
    """Check the health of the AI Chat module."""
    service = get_service()
    return service.health_check()
