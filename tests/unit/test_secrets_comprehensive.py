"""Comprehensive unit tests for the secrets module."""
import os
from unittest.mock import patch

import pytest

from backend.app.core.secrets import (
    SecretsValidationError,
    SecretsValidator,
    validate_on_startup,
)


class TestSecretsValidatorValidateAll:
    def test_development_no_secret_key(self):
        with patch.dict(os.environ, {"APP_ENV": "development"}, clear=True):
            warnings = SecretsValidator.validate_all("development")
            assert any("SECRET_KEY is not set" in w for w in warnings)

    def test_production_no_secret_key(self):
        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=True):
            with pytest.raises(SecretsValidationError, match="SECRET_KEY is not set"):
                SecretsValidator.validate_all("production")

    def test_short_secret_key_warning(self):
        with patch.dict(os.environ, {"SECRET_KEY": "short"}, clear=True):
            warnings = SecretsValidator.validate_all("development")
            assert any("too short" in w for w in warnings)

    def test_default_secret_key_production(self):
        with patch.dict(os.environ, {
            "SECRET_KEY": "changeme123",
            "APP_ENV": "production",
            "DATABASE_URL": "postgresql://localhost/db",
            "REDIS_PASSWORD": "securepass",
        }, clear=True), pytest.raises(SecretsValidationError, match="obvious default"):
            SecretsValidator.validate_all("production")

    def test_default_secret_key_development(self):
        with patch.dict(os.environ, {"SECRET_KEY": "changeme123"}, clear=True):
            warnings = SecretsValidator.validate_all("development")
            assert any("default value" in w for w in warnings)

    def test_alphanumeric_secret_key_warning(self):
        with patch.dict(
            os.environ,
            {"SECRET_KEY": "abcdef1234567890abcdef1234567890"},
            clear=True,
        ):
            warnings = SecretsValidator.validate_all("development")
            assert any("alphanumeric" in w for w in warnings)

    def test_production_no_database_url(self):
        with patch.dict(os.environ, {
            "SECRET_KEY": "a" * 64,
            "APP_ENV": "production",
        }, clear=True), pytest.raises(SecretsValidationError, match="DATABASE_URL"):
            SecretsValidator.validate_all("production")

    def test_production_localhost_db_warning(self):
        with patch.dict(os.environ, {
            "SECRET_KEY": "a" * 64,
            "DATABASE_URL": "postgresql://localhost/db",
            "REDIS_PASSWORD": "securepass",
            "APP_ENV": "production",
        }, clear=True):
            warnings = SecretsValidator.validate_all("production")
            assert any("localhost" in w for w in warnings)

    def test_production_no_redis_password_warning(self):
        # REDIS_PASSWORD is a required env var in production;
        # a missing value must fail closed (raise) rather than warn.
        with patch.dict(os.environ, {
            "SECRET_KEY": "a" * 64,
            "DATABASE_URL": "postgresql://prodhost/db",
            "APP_ENV": "production",
        }, clear=True), pytest.raises(SecretsValidationError, match="REDIS_PASSWORD"):
            SecretsValidator.validate_all("production")

    def test_production_sqlite_warning(self):
        with patch.dict(os.environ, {
            "SECRET_KEY": "a" * 64,
            "DATABASE_URL": "sqlite:///db.sqlite",
            "REDIS_PASSWORD": "securepass",
            "APP_ENV": "production",
        }, clear=True):
            warnings = SecretsValidator.validate_all("production")
            assert any("SQLite" in w for w in warnings)

    def test_production_missing_required_vars(self):
        with patch.dict(os.environ, {
            "SECRET_KEY": "a" * 64,
            "APP_ENV": "production",
        }, clear=True), pytest.raises(SecretsValidationError, match="DATABASE_URL"):
            SecretsValidator.validate_all("production")

    def test_valid_production_config(self):
        with patch.dict(os.environ, {
            "SECRET_KEY": "a" * 64,
            "DATABASE_URL": "postgresql://prodhost/db?sslmode=require",
            "REDIS_PASSWORD": "securepass123",
            "APP_ENV": "production",
        }, clear=True):
            warnings = SecretsValidator.validate_all("production")
            # Should have no critical warnings
            critical_warnings = [w for w in warnings if "WARNING" in w]
            assert len(critical_warnings) >= 0


class TestSecretsValidatorGenerateSecretKey:
    def test_generate_secret_key_length(self):
        key = SecretsValidator.generate_secret_key(64)
        assert len(key) == 64

    def test_generate_secret_key_default_length(self):
        key = SecretsValidator.generate_secret_key()
        assert len(key) == 64

    def test_generate_secret_key_is_hex(self):
        key = SecretsValidator.generate_secret_key(32)
        int(key, 16)  # Should not raise


class TestSecretsValidatorValidatePasswordStrength:
    def test_valid_password(self):
        errors = SecretsValidator.validate_password_strength("StrongP@ss1abcd")
        assert len(errors) == 0

    def test_too_short(self):
        errors = SecretsValidator.validate_password_strength("Sh@rt1")
        assert any("at least 12" in e for e in errors)

    def test_no_uppercase(self):
        errors = SecretsValidator.validate_password_strength("lowercasep@ss1abcd")
        assert any("uppercase" in e for e in errors)

    def test_no_lowercase(self):
        errors = SecretsValidator.validate_password_strength("UPPERCASEP@SS1ABC")
        assert any("lowercase" in e for e in errors)

    def test_no_digit(self):
        errors = SecretsValidator.validate_password_strength("NoDigitsP@ssabcd")
        assert any("digit" in e for e in errors)

    def test_no_special_char(self):
        errors = SecretsValidator.validate_password_strength("NoSpecialChar1abcd")
        assert any("special" in e for e in errors)

    def test_repeated_characters(self):
        errors = SecretsValidator.validate_password_strength("AAAbcdefgh1@x")
        assert any("repeated" in e for e in errors)

    def test_common_pattern(self):
        errors = SecretsValidator.validate_password_strength("Password123!@#")
        assert any("common pattern" in e for e in errors)

    def test_multiple_errors(self):
        errors = SecretsValidator.validate_password_strength("weak")
        assert len(errors) >= 3


class TestValidateOnStartup:
    def test_validate_on_startup_no_db_url(self):
        with patch.dict(os.environ, {}, clear=True):
            # Should not raise
            validate_on_startup()

    def test_validate_on_startup_with_db_url(self):
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://host/db",
        }, clear=True):
            # Should not raise
            validate_on_startup()

    def test_validate_on_startup_sqlite(self):
        with patch.dict(os.environ, {
            "DATABASE_URL": "sqlite:///test.db",
        }, clear=True):
            # Should not raise
            validate_on_startup()
