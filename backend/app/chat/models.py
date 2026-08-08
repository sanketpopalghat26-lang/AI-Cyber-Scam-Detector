"""
AI Chat Security Assistant Models
===================================
SQLModel ORM models for chat sessions, messages, and RAG document chunks.
"""

from datetime import UTC, datetime
from enum import Enum

from sqlmodel import JSON, Field, Relationship, SQLModel, Text


def _utcnow() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


class ChatRole(str, Enum):
    """Role of a chat message author."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatIntent(str, Enum):
    """Detected intent of a user query."""

    EXPLAIN_PREDICTION = "explain_prediction"
    EXPLAIN_URL = "explain_url"
    GENERATE_REPORT = "generate_report"
    TODAY_ATTACKS = "today_attacks"
    COMPARE_PREDICTIONS = "compare_predictions"
    THREAT_LOOKUP = "threat_lookup"
    HELP = "help"
    GENERAL = "general"


class ChatSession(SQLModel, table=True):
    """A chat session belonging to a user."""

    __tablename__ = "chat_sessions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(
        default=None, foreign_key="users.id", index=True
    )
    title: str = Field(default="New Chat", max_length=500)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False, index=True)
    updated_at: datetime | None = Field(
        default=None, sa_column_kwargs={"onupdate": _utcnow}
    )

    messages: list["ChatMessage"] = Relationship(back_populates="session")


class ChatMessage(SQLModel, table=True):
    """A single message within a chat session."""

    __tablename__ = "chat_messages"

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(
        foreign_key="chat_sessions.id", nullable=False, index=True
    )
    role: ChatRole = Field(nullable=False, index=True)
    content: str = Field(nullable=False, sa_type=Text)
    intent: ChatIntent | None = Field(default=None, index=True)
    # RAG context references (JSON list of retrieved document metadata)
    retrieved_context: dict | None = Field(
        default=None, sa_type=JSON, description="Metadata of retrieved documents"
    )
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    model: str | None = Field(default=None, max_length=100)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False, index=True)

    session: "ChatSession" = Relationship(back_populates="messages")


class ChatDocumentChunk(SQLModel, table=True):
    """
    A chunk of a source document used for RAG retrieval.

    Stores the text content plus a semantic embedding vector (as JSON)
    and metadata for retrieval and ranking.
    """

    __tablename__ = "chat_document_chunks"

    id: int | None = Field(default=None, primary_key=True)
    source_type: str = Field(
        nullable=False, index=True, max_length=100
    )  # scan, report, threat_ioc, analysis, case, etc.
    source_id: int | None = Field(default=None, index=True)
    content: str = Field(nullable=False, sa_type=Text)
    embedding: list[float] | None = Field(
        default=None, sa_type=JSON, description="Semantic embedding vector"
    )
    tokens_count: int = Field(default=0)
    metadata_json: dict | None = Field(
        default=None, sa_type=JSON, description="Structured metadata for retrieval"
    )
    created_at: datetime = Field(default_factory=_utcnow, nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<ChatDocumentChunk id={self.id} source={self.source_type}:{self.source_id}>"
