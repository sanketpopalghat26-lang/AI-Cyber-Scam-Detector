import os
from dataclasses import dataclass


@dataclass
class ConfigValidationIssue:
    name: str
    message: str


class SettingsValidationError(ValueError):
    pass


def validate_environment() -> list[ConfigValidationIssue]:
    issues: list[ConfigValidationIssue] = []
    secret_key = os.getenv("SECRET_KEY", "")
    if not secret_key or secret_key in {"changeme123", "secret", "dev-secret"}:
        issues.append(ConfigValidationIssue("SECRET_KEY", "SECRET_KEY is missing or uses a default development value."))

    database_url = os.getenv("DATABASE_URL", "")
    if database_url and database_url.startswith("sqlite") and ":memory:" not in database_url:
        issues.append(ConfigValidationIssue("DATABASE_URL", "SQLite file-based database URLs are fine for local use but should be explicitly managed in production."))

    return issues


def require_production_ready() -> None:
    issues = validate_environment()
    if issues:
        raise SettingsValidationError(
            "Environment validation failed: " + "; ".join(f"{issue.name}: {issue.message}" for issue in issues)
        )
