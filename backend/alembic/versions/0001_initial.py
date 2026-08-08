"""
Initial migration for AI Cyber Scam Detector.

Creates all core, investigation, and threat intelligence tables.
Revision ID: 0001_initial
Revises:
Create Date: 2024-07-30
"""
import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create core application tables."""
    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_is_admin", "users", ["is_admin"])
    op.create_index("ix_users_is_active", "users", ["is_active"])

    # ------------------------------------------------------------------
    # scans
    # ------------------------------------------------------------------
    op.create_table(
        "scans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("result", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("model_version", sa.String(), nullable=True),
        sa.Column("processing_time_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scans_user_id", "scans", ["user_id"])
    op.create_index("ix_scans_result", "scans", ["result"])
    op.create_index("ix_scans_source", "scans", ["source"])
    op.create_index("ix_scans_created_at", "scans", ["created_at"])
    op.create_index("ix_scans_user_result", "scans", ["user_id", "result", "created_at"])

    # ------------------------------------------------------------------
    # reports
    # ------------------------------------------------------------------
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("scan_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reports_user_id", "reports", ["user_id"])
    op.create_index("ix_reports_scan_id", "reports", ["scan_id"])
    op.create_index("ix_reports_created_at", "reports", ["created_at"])

    # ------------------------------------------------------------------
    # feedbacks
    # ------------------------------------------------------------------
    op.create_table(
        "feedbacks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feedbacks_user_id", "feedbacks", ["user_id"])
    op.create_index("ix_feedbacks_created_at", "feedbacks", ["created_at"])

    # ------------------------------------------------------------------
    # logs
    # ------------------------------------------------------------------
    op.create_table(
        "logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("level", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_logs_user_id", "logs", ["user_id"])
    op.create_index("ix_logs_level", "logs", ["level"])
    op.create_index("ix_logs_correlation_id", "logs", ["correlation_id"])
    op.create_index("ix_logs_created_at", "logs", ["created_at"])


def downgrade() -> None:
    """Drop all tables (reverse order)."""
    op.drop_index("ix_logs_created_at", table_name="logs")
    op.drop_index("ix_logs_correlation_id", table_name="logs")
    op.drop_index("ix_logs_level", table_name="logs")
    op.drop_index("ix_logs_user_id", table_name="logs")
    op.drop_table("logs")

    op.drop_index("ix_feedbacks_created_at", table_name="feedbacks")
    op.drop_index("ix_feedbacks_user_id", table_name="feedbacks")
    op.drop_table("feedbacks")

    op.drop_index("ix_reports_created_at", table_name="reports")
    op.drop_index("ix_reports_scan_id", table_name="reports")
    op.drop_index("ix_reports_user_id", table_name="reports")
    op.drop_table("reports")

    op.drop_index("ix_scans_user_result", table_name="scans")
    op.drop_index("ix_scans_created_at", table_name="scans")
    op.drop_index("ix_scans_source", table_name="scans")
    op.drop_index("ix_scans_result", table_name="scans")
    op.drop_index("ix_scans_user_id", table_name="scans")
    op.drop_table("scans")

    op.drop_index("ix_users_is_active", table_name="users")
    op.drop_index("ix_users_is_admin", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
