"""
AI Chat Security Assistant Schemas
====================================
Pydantic request/response models for the RAG-based chat assistant.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from .models import ChatIntent, ChatRole


def _utcnow() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


# =============================================================================
# Request Models
# =============================================================================


class ChatRequest(BaseModel):
    """A chat message request from the user."""

    message: str = Field(
        ..., min_length=1, max_length=10000, description="User's natural language query"
    )
    session_id: int | None = Field(
        default=None, description="Existing chat session ID (optional; creates new if absent)"
    )
    source: str | None = Field(
        default="chat", max_length=50, description="Source of the query"
    )


class ChatSessionCreate(BaseModel):
    """Create a new chat session."""

    title: str | None = Field(default="New Chat", max_length=500)


# =============================================================================
# Response Models
# =============================================================================


class RetrievedContext(BaseModel):
    """A retrieved RAG context document."""

    source_type: str = Field(..., description="Source type (scan, report, threat, etc.)")
    source_id: int | None = Field(default=None)
    content: str = Field(..., description="Truncated content of the retrieved document")
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatMessageOut(BaseModel):
    """A chat message in responses."""

    id: int
    session_id: int
    role: ChatRole
    content: str
    intent: ChatIntent | None = None
    retrieved_context: list[RetrievedContext] | None = None
    confidence: float | None = None
    model: str | None = None
    created_at: str


class ChatSessionOut(BaseModel):
    """A chat session summary."""

    id: int
    user_id: int | None = None
    title: str
    is_active: bool = True
    created_at: str
    updated_at: str | None = None


class ChatResponse(BaseModel):
    """The assistant's response to a chat message."""

    message: ChatMessageOut
    session_id: int
    intent: ChatIntent
    response: str = Field(..., description="The assistant's natural language answer")
    sources: list[RetrievedContext] = Field(
        default_factory=list, description="Retrieved RAG sources"
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    model: str
    processing_time_ms: float = Field(..., ge=0.0)
    suggestions: list[str] = Field(
        default_factory=list, description="Suggested follow-up questions"
    )


class ChatIntentResponse(BaseModel):
    """Result of intent detection on a query."""

    message: str
    intent: ChatIntent
    confidence: float = Field(..., ge=0.0, le=1.0)
    matched_keywords: list[str] = Field(default_factory=list)


class ChatHistoryResponse(BaseModel):
    """Full message history for a session."""

    session: ChatSessionOut
    messages: list[ChatMessageOut]
    total: int
