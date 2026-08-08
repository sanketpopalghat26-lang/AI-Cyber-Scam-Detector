"""
Enterprise API Schemas
=======================
Pydantic models for request/response validation.
Implements strict input validation and sanitization.
"""

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# =============================================================================
# Authentication Schemas
# =============================================================================

class Token(BaseModel):
    """Legacy token response (single access token)."""
    access_token: str
    token_type: str = 'bearer'


class TokenResponse(BaseModel):
    """Enterprise token response with refresh token support."""
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'
    expires_in: int = Field(default=86400, description="TTL in seconds")


class RefreshRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str = Field(..., min_length=10, description="Valid refresh token")


class TokenData(BaseModel):
    """Decoded token payload."""
    username: str


class UserCreate(BaseModel):
    """User registration request with validation."""
    email: str = Field(..., min_length=5, max_length=255, description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate and normalize email address."""
        v = v.lower().strip()
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid email format")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserOut(BaseModel):
    """User profile response."""
    id: int
    email: str
    is_admin: bool
    created_at: str | None = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Prediction Schemas
# =============================================================================

class FeedbackCreate(BaseModel):
    """Feedback submission with validation."""
    message: str = Field(..., min_length=1, max_length=2000, description="Feedback message")

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        """Sanitize feedback message."""
        return v.strip()[:2000]


class PredictRequest(BaseModel):
    """Prediction request with input validation."""
    text: str = Field(..., min_length=1, max_length=10000, description="Text to analyze")
    source: str | None = Field(default='generic', max_length=50, description="Source of the text")

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        """Sanitize input text."""
        v = v.strip()
        if not v:
            raise ValueError("Text must not be empty")
        # Remove potentially dangerous characters
        v = v.replace("\x00", "")  # Remove null bytes
        return v


class PredictResponse(BaseModel):
    """Prediction response with explanation."""
    label: str = Field(..., pattern="^(safe|suspicious|scam)$")
    confidence: float = Field(..., ge=0.0, le=1.0)
    explanation: dict[str, Any]


class ScanOut(BaseModel):
    """Scan record for history display."""
    id: int
    input_text: str = Field(..., max_length=200)
    result: str
    confidence: float
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class DashboardStats(BaseModel):
    """Dashboard statistics."""
    total_scans: int
    scam_percentage: float = Field(..., ge=0.0, le=100.0)
    safe_percentage: float = Field(..., ge=0.0, le=100.0)
    recent_scans: list[ScanOut]


# (FeedbackCreate is defined above in the Prediction Schemas section)

