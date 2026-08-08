"""
Add AI Chat Security Assistant tables.

Revision ID: 0003_chat
Revises: 0002_threat_and_investigation
Create Date: 2024-07-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_chat"
down_revision = "0002_threat_and_investigation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create chat session, message, and RAG document chunk tables."""

    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])
    op.create_index("ix_chat_sessions_is_active", "chat_sessions", ["is_active"])
    op.create_index("ix_chat_sessions_created_at", "chat_sessions", ["created_at"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(), nullable=True),
        sa.Column("retrieved_context", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])
    op.create_index("ix_chat_messages_role", "chat_messages", ["role"])
    op.create_index("ix_chat_messages_intent", "chat_messages", ["intent"])
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])

    op.create_table(
        "chat_document_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=100), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("tokens_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_document_chunks_source_type", "chat_document_chunks", ["source_type"])
    op.create_index("ix_chat_document_chunks_source_id", "chat_document_chunks", ["source_id"])
    op.create_index("ix_chat_document_chunks_created_at", "chat_document_chunks", ["created_at"])


def downgrade() -> None:
    """Drop chat tables (reverse order)."""
    op.drop_index("ix_chat_document_chunks_created_at", table_name="chat_document_chunks")
    op.drop_index("ix_chat_document_chunks_source_id", table_name="chat_document_chunks")
    op.drop_index("ix_chat_document_chunks_source_type", table_name="chat_document_chunks")
    op.drop_table("chat_document_chunks")

    op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_intent", table_name="chat_messages")
    op.drop_index("ix_chat_messages_role", table_name="chat_messages")
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_table("chat_messages")

    op.drop_index("ix_chat_sessions_created_at", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_is_active", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_user_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")

