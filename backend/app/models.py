"""
Enterprise Database Models
============================
SQLModel ORM models for all entities.
Includes indexes, constraints, and relationships.
"""

from datetime import UTC, datetime

from sqlmodel import Field, Relationship, SQLModel


def _utcnow() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


# =============================================================================
# User Model
# =============================================================================

class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, nullable=False)
    hashed_password: str = Field(nullable=False)
    is_admin: bool = Field(default=False, index=True)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime | None = Field(default=None, sa_column_kwargs={"onupdate": _utcnow})
    last_login: datetime | None = Field(default=None)

    # Relationships
    scans: list["Scan"] = Relationship(back_populates="user")
    reports: list["Report"] = Relationship(back_populates="user")
    feedbacks: list["Feedback"] = Relationship(back_populates="user")
    logs: list["Log"] = Relationship(back_populates="user")


# =============================================================================
# Scan Model
# =============================================================================

class Scan(SQLModel, table=True):
    __tablename__ = "scans"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    input_text: str = Field(nullable=False)
    result: str = Field(nullable=False, index=True)
    confidence: float = Field(nullable=False)
    source: str = Field(default='generic', index=True)
    model_version: str | None = Field(default=None)
    processing_time_ms: float | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow, index=True)

    # Relationships
    user: User | None = Relationship(back_populates="scans")
    reports: list["Report"] = Relationship(back_populates="scan")


# =============================================================================
# Report Model
# =============================================================================

class Report(SQLModel, table=True):
    __tablename__ = "reports"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    scan_id: int | None = Field(default=None, foreign_key="scans.id", index=True)
    title: str = Field(nullable=False)
    content: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=_utcnow, index=True)

    # Relationships
    user: User | None = Relationship(back_populates="reports")
    scan: Scan | None = Relationship(back_populates="reports")


# =============================================================================
# Feedback Model
# =============================================================================

class Feedback(SQLModel, table=True):
    __tablename__ = "feedbacks"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    message: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=_utcnow, index=True)

    # Relationships
    user: User | None = Relationship(back_populates="feedbacks")


# =============================================================================
# Log Model
# =============================================================================

class Log(SQLModel, table=True):
    __tablename__ = "logs"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    level: str = Field(default='info', index=True)
    message: str = Field(nullable=False)
    correlation_id: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=_utcnow, index=True)

    # Relationships
    user: User | None = Relationship(back_populates="logs")

