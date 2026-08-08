"""
Add threat intelligence and investigation tables.

Revision ID: 0002_threat_and_investigation
Revises: 0001_initial
Create Date: 2024-07-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_threat_and_investigation"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create threat intelligence and investigation tables."""

    # ==================================================================
    # Threat Intelligence
    # ==================================================================
    op.create_table(
        "threat_iocs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ioc_value", sa.Text(), nullable=False),
        sa.Column("ioc_type", sa.String(), nullable=False),
        sa.Column("threat_category", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("severity", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("source_reference", sa.String(), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("country_code", sa.String(length=5), nullable=True),
        sa.Column("asn", sa.String(length=20), nullable=True),
        sa.Column("asn_org", sa.String(), nullable=True),
        sa.Column("isp", sa.String(), nullable=True),
        sa.Column("domain_registrar", sa.String(), nullable=True),
        sa.Column("domain_created", sa.DateTime(timezone=True), nullable=True),
        sa.Column("domain_expires", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reverse_dns", sa.String(), nullable=True),
        sa.Column("tags", sa.String(), nullable=True),
        sa.Column("extra_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_threat_iocs_ioc_value", "threat_iocs", ["ioc_value"])
    op.create_index("ix_threat_iocs_ioc_type", "threat_iocs", ["ioc_type"])
    op.create_index("ix_threat_iocs_threat_category", "threat_iocs", ["threat_category"])
    op.create_index("ix_threat_iocs_status", "threat_iocs", ["status"])
    op.create_index("ix_threat_iocs_source", "threat_iocs", ["source"])
    op.create_index("ix_threat_iocs_first_seen", "threat_iocs", ["first_seen"])
    op.create_index("ix_threat_iocs_last_seen", "threat_iocs", ["last_seen"])
    op.create_index("ix_threat_iocs_country_code", "threat_iocs", ["country_code"])

    op.create_table(
        "threat_feeds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_update", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_update", sa.DateTime(timezone=True), nullable=True),
        sa.Column("update_interval", sa.Integer(), nullable=False),
        sa.Column("total_iocs_imported", sa.Integer(), nullable=False),
        sa.Column("total_iocs_active", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("feed_metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source"),
    )
    op.create_index("ix_threat_feeds_source", "threat_feeds", ["source"])
    op.create_index("ix_threat_feeds_enabled", "threat_feeds", ["enabled"])

    op.create_table(
        "threat_analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ioc_id", sa.Integer(), nullable=True),
        sa.Column("query_value", sa.Text(), nullable=False),
        sa.Column("query_type", sa.String(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(), nullable=False),
        sa.Column("threat_category", sa.String(), nullable=False),
        sa.Column("is_malicious", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("sources_checked", sa.Integer(), nullable=False),
        sa.Column("positive_detections", sa.Integer(), nullable=False),
        sa.Column("total_detections", sa.Integer(), nullable=False),
        sa.Column("provider_results", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("geoip_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("dns_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("whois_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("asn_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("tags", sa.String(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("processing_time_ms", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ioc_id"], ["threat_iocs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_threat_analyses_ioc_id", "threat_analyses", ["ioc_id"])
    op.create_index("ix_threat_analyses_query_value", "threat_analyses", ["query_value"])
    op.create_index("ix_threat_analyses_query_type", "threat_analyses", ["query_type"])
    op.create_index("ix_threat_analyses_risk_level", "threat_analyses", ["risk_level"])
    op.create_index("ix_threat_analyses_threat_category", "threat_analyses", ["threat_category"])
    op.create_index("ix_threat_analyses_is_malicious", "threat_analyses", ["is_malicious"])
    op.create_index("ix_threat_analyses_user_id", "threat_analyses", ["user_id"])
    op.create_index("ix_threat_analyses_created_at", "threat_analyses", ["created_at"])

    op.create_table(
        "threat_timeline",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("ioc_id", sa.Integer(), nullable=True),
        sa.Column("feed_id", sa.Integer(), nullable=True),
        sa.Column("analysis_id", sa.Integer(), nullable=True),
        sa.Column("extra_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["threat_analyses.id"]),
        sa.ForeignKeyConstraint(["feed_id"], ["threat_feeds.id"]),
        sa.ForeignKeyConstraint(["ioc_id"], ["threat_iocs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_threat_timeline_event_type", "threat_timeline", ["event_type"])
    op.create_index("ix_threat_timeline_severity", "threat_timeline", ["severity"])
    op.create_index("ix_threat_timeline_ioc_id", "threat_timeline", ["ioc_id"])
    op.create_index("ix_threat_timeline_feed_id", "threat_timeline", ["feed_id"])
    op.create_index("ix_threat_timeline_analysis_id", "threat_timeline", ["analysis_id"])
    op.create_index("ix_threat_timeline_created_at", "threat_timeline", ["created_at"])

    op.create_table(
        "threat_risk_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ioc_id", sa.Integer(), nullable=True),
        sa.Column("score_value", sa.Float(), nullable=False),
        sa.Column("score_components", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("calculation_version", sa.String(length=20), nullable=False),
        sa.Column("risk_level", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ioc_id"], ["threat_iocs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_threat_risk_scores_ioc_id", "threat_risk_scores", ["ioc_id"])
    op.create_index("ix_threat_risk_scores_risk_level", "threat_risk_scores", ["risk_level"])
    op.create_index("ix_threat_risk_scores_created_at", "threat_risk_scores", ["created_at"])

    # ==================================================================
    # Investigation
    # ==================================================================
    op.create_table(
        "investigation_cases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.String(length=10000), nullable=False),
        sa.Column("case_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("priority", sa.String(), nullable=False),
        sa.Column("assigned_to", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("related_scan_id", sa.Integer(), nullable=True),
        sa.Column("related_threat_id", sa.Integer(), nullable=True),
        sa.Column("tags", sa.String(length=2000), nullable=False),
        sa.Column("findings", sa.String(length=50000), nullable=False),
        sa.Column("resolution_notes", sa.String(length=10000), nullable=False),
        sa.Column("financial_loss_estimate", sa.Float(), nullable=True),
        sa.Column("affected_users_count", sa.Integer(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["related_scan_id"], ["scans.id"]),
        sa.ForeignKeyConstraint(["related_threat_id"], ["threat_iocs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_investigation_cases_status", "investigation_cases", ["status"])
    op.create_index("ix_investigation_cases_priority", "investigation_cases", ["priority"])
    op.create_index("ix_investigation_cases_assigned_to", "investigation_cases", ["assigned_to"])
    op.create_index("ix_investigation_cases_created_by", "investigation_cases", ["created_by"])
    op.create_index("ix_investigation_cases_is_archived", "investigation_cases", ["is_archived"])
    op.create_index("ix_investigation_cases_created_at", "investigation_cases", ["created_at"])

    op.create_table(
        "investigation_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("evidence_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.String(length=5000), nullable=False),
        sa.Column("content", sa.String(length=50000), nullable=False),
        sa.Column("source", sa.String(length=500), nullable=False),
        sa.Column("collected_by", sa.Integer(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("metadata_json", sa.String(length=10000), nullable=False),
        sa.Column("hash_value", sa.String(length=128), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("verified_by", sa.Integer(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["investigation_cases.id"]),
        sa.ForeignKeyConstraint(["collected_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_investigation_evidence_case_id", "investigation_evidence", ["case_id"])

    op.create_table(
        "investigation_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.String(length=10000), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["investigation_cases.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_investigation_notes_case_id", "investigation_notes", ["case_id"])

    op.create_table(
        "investigation_attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["investigation_cases.id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_investigation_attachments_case_id", "investigation_attachments", ["case_id"])

    op.create_table(
        "investigation_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=5000), nullable=False),
        sa.Column("previous_value", sa.String(length=2000), nullable=False),
        sa.Column("new_value", sa.String(length=2000), nullable=False),
        sa.Column("performed_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["investigation_cases.id"]),
        sa.ForeignKeyConstraint(["performed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_investigation_history_case_id", "investigation_history", ["case_id"])
    op.create_index("ix_investigation_history_created_at", "investigation_history", ["created_at"])


def downgrade() -> None:
    """Drop threat intelligence and investigation tables (reverse order)."""
    op.drop_index("ix_investigation_history_created_at", table_name="investigation_history")
    op.drop_index("ix_investigation_history_case_id", table_name="investigation_history")
    op.drop_table("investigation_history")

    op.drop_index("ix_investigation_attachments_case_id", table_name="investigation_attachments")
    op.drop_table("investigation_attachments")

    op.drop_index("ix_investigation_notes_case_id", table_name="investigation_notes")
    op.drop_table("investigation_notes")

    op.drop_index("ix_investigation_evidence_case_id", table_name="investigation_evidence")
    op.drop_table("investigation_evidence")

    op.drop_index("ix_investigation_cases_created_at", table_name="investigation_cases")
    op.drop_index("ix_investigation_cases_is_archived", table_name="investigation_cases")
    op.drop_index("ix_investigation_cases_created_by", table_name="investigation_cases")
    op.drop_index("ix_investigation_cases_assigned_to", table_name="investigation_cases")
    op.drop_index("ix_investigation_cases_priority", table_name="investigation_cases")
    op.drop_index("ix_investigation_cases_status", table_name="investigation_cases")
    op.drop_table("investigation_cases")

    op.drop_index("ix_threat_risk_scores_created_at", table_name="threat_risk_scores")
    op.drop_index("ix_threat_risk_scores_risk_level", table_name="threat_risk_scores")
    op.drop_index("ix_threat_risk_scores_ioc_id", table_name="threat_risk_scores")
    op.drop_table("threat_risk_scores")

    op.drop_index("ix_threat_timeline_created_at", table_name="threat_timeline")
    op.drop_index("ix_threat_timeline_analysis_id", table_name="threat_timeline")
    op.drop_index("ix_threat_timeline_feed_id", table_name="threat_timeline")
    op.drop_index("ix_threat_timeline_ioc_id", table_name="threat_timeline")
    op.drop_index("ix_threat_timeline_severity", table_name="threat_timeline")
    op.drop_index("ix_threat_timeline_event_type", table_name="threat_timeline")
    op.drop_table("threat_timeline")

    op.drop_index("ix_threat_analyses_created_at", table_name="threat_analyses")
    op.drop_index("ix_threat_analyses_user_id", table_name="threat_analyses")
    op.drop_index("ix_threat_analyses_is_malicious", table_name="threat_analyses")
    op.drop_index("ix_threat_analyses_threat_category", table_name="threat_analyses")
    op.drop_index("ix_threat_analyses_risk_level", table_name="threat_analyses")
    op.drop_index("ix_threat_analyses_query_type", table_name="threat_analyses")
    op.drop_index("ix_threat_analyses_query_value", table_name="threat_analyses")
    op.drop_index("ix_threat_analyses_ioc_id", table_name="threat_analyses")
    op.drop_table("threat_analyses")

    op.drop_index("ix_threat_feeds_enabled", table_name="threat_feeds")
    op.drop_index("ix_threat_feeds_source", table_name="threat_feeds")
    op.drop_table("threat_feeds")

    op.drop_index("ix_threat_iocs_country_code", table_name="threat_iocs")
    op.drop_index("ix_threat_iocs_last_seen", table_name="threat_iocs")
    op.drop_index("ix_threat_iocs_first_seen", table_name="threat_iocs")
    op.drop_index("ix_threat_iocs_source", table_name="threat_iocs")
    op.drop_index("ix_threat_iocs_status", table_name="threat_iocs")
    op.drop_index("ix_threat_iocs_threat_category", table_name="threat_iocs")
    op.drop_index("ix_threat_iocs_ioc_type", table_name="threat_iocs")
    op.drop_index("ix_threat_iocs_ioc_value", table_name="threat_iocs")
    op.drop_table("threat_iocs")
