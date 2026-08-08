"""Validate Alembic migrations end-to-end (upgrade + downgrade round-trip)."""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from alembic import command
from alembic.config import Config

EXPECTED_TABLES = {
    # Core
    "users", "scans", "reports", "feedbacks", "logs",
    # Threat intelligence
    "threat_iocs", "threat_feeds", "threat_analyses",
    "threat_timeline", "threat_risk_scores",
    # Investigation
    "investigation_cases", "investigation_evidence", "investigation_notes",
    "investigation_attachments", "investigation_history",
}


def main() -> int:
    db_path = os.path.join(
        os.path.dirname(__file__), "..", "backend", "migration_test.db"
    )
    if os.path.exists(db_path):
        os.remove(db_path)

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    cfg = Config()
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "backend", "alembic"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

    # Upgrade to head
    command.upgrade(cfg, "head")
    print("Upgrade to head: OK")

    conn = sqlite3.connect(db_path)
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
        )
    }
    conn.close()

    missing = EXPECTED_TABLES - tables
    if missing:
        print(f"FAIL: missing tables {sorted(missing)}")
        return 1
    print(f"All {len(EXPECTED_TABLES)} expected tables present: OK")

    # Check alembic version
    conn = sqlite3.connect(db_path)
    version = list(conn.execute("SELECT version_num FROM alembic_version"))
    conn.close()
    print(f"Alembic version: {version}")

    # Downgrade to base
    command.downgrade(cfg, "base")
    print("Downgrade to base: OK")

    conn = sqlite3.connect(db_path)
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
        )
    }
    conn.close()
    if tables:
        print(f"FAIL: tables remain after downgrade: {sorted(tables)}")
        return 1
    print("Downgrade clean (no tables remain): OK")

    print("\n=== MIGRATION VALIDATION PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
