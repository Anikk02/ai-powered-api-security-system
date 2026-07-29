# 📦 Pydantic Schemas — JWT Authentication

> Request/Response validation for all auth endpoints

---

## Overview

All schemas use **Pydantic v2** (matching the project's `pydantic_settings` dependency).
Place this file at: `backend/app/schemas/auth.py`

---

## File: `app/schemas/auth.py`

```python
"""
Pydantic schemas for JWT authentication system.
Place this file at: backend/app/schemas/auth.py
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional
import re


# ============================================================
# REGISTRATION
# ============================================================

class ClientRegister(BaseModel):
    """Schema for client registration."""
    
    email: EmailStr = Field(
        ...,
        description="Client email address",
        examples=["user@company.com"]
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (min 8 chars, must include uppercase, lowercase, digit)",
        examples=["SecurePass123"]
    )
    company_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Company or organization name",
        examples=["Acme Corp"]
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Enforce password complexity rules."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class ClientRegisterResponse(BaseModel):
    """Response after successful registration."""
    
    id: int
    email: str
    company_name: Optional[str] = None
    role: str
    status: str
    message: str = "Registration successful"
    
    model_config = {"from_attributes": True}


# ============================================================
# LOGIN
# ============================================================

class ClientLogin(BaseModel):
    """Schema for client login."""
    
    email: EmailStr = Field(
        ...,
        description="Registered email address",
        examples=["user@company.com"]
    )
    password: str = Field(
        ...,
        description="Account password",
        examples=["SecurePass123"]
    )


class TokenResponse(BaseModel):
    """JWT token pair response."""
    
    access_token: str = Field(
        ...,
        description="Short-lived JWT access token (30 min)"
    )
    refresh_token: str = Field(
        ...,
        description="Long-lived refresh token (7 days)"
    )
    token_type: str = Field(
        default="bearer",
        description="Token type (always 'bearer')"
    )
    expires_in: int = Field(
        ...,
        description="Access token expiry in seconds",
        examples=[1800]
    )


# ============================================================
# TOKEN REFRESH
# ============================================================

class TokenRefreshRequest(BaseModel):
    """Request to refresh an access token."""
    
    refresh_token: str = Field(
        ...,
        description="Valid refresh token from login"
    )


class TokenRefreshResponse(BaseModel):
    """Response with new access token."""
    
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ============================================================
# PASSWORD RESET
# ============================================================

class ForgotPasswordRequest(BaseModel):
    """Request a password reset link."""
    
    email: EmailStr = Field(
        ...,
        description="Email address for password reset",
        examples=["user@company.com"]
    )


class ForgotPasswordResponse(BaseModel):
    """Response after requesting password reset."""
    
    message: str = "If the email exists, a reset link has been sent"
    # In development mode, include the token for testing
    reset_token: Optional[str] = Field(
        None,
        description="Reset token (only returned in development mode)"
    )


class ResetPasswordRequest(BaseModel):
    """Reset password with a valid reset token."""
    
    token: str = Field(
        ...,
        description="Password reset token"
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password"
    )

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Same password rules as registration."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class ResetPasswordResponse(BaseModel):
    """Response after successful password reset."""
    
    message: str = "Password reset successful. Please login with your new password."


# ============================================================
# LOGOUT
# ============================================================

class LogoutRequest(BaseModel):
    """Logout and revoke refresh token."""
    
    refresh_token: str = Field(
        ...,
        description="Refresh token to revoke"
    )


class LogoutResponse(BaseModel):
    """Response after successful logout."""
    
    message: str = "Logged out successfully"


# ============================================================
# CLIENT PROFILE
# ============================================================

class ClientProfile(BaseModel):
    """Client profile response (for /auth/me endpoint)."""
    
    id: int
    email: str
    company_name: Optional[str] = None
    role: str
    status: str
    email_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None
    
    model_config = {"from_attributes": True}


# ============================================================
# ERROR RESPONSES
# ============================================================

class AuthError(BaseModel):
    """Standard error response for auth endpoints."""
    
    detail: str = Field(
        ...,
        description="Error message",
        examples=["Invalid credentials"]
    )
    error_code: Optional[str] = Field(
        None,
        description="Machine-readable error code",
        examples=["INVALID_CREDENTIALS"]
    )


# ============================================================
# CHANGE PASSWORD (authenticated)
# ============================================================

class ChangePasswordRequest(BaseModel):
    """Change password while logged in."""
    
    current_password: str = Field(
        ...,
        description="Current account password"
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password"
    )

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class ChangePasswordResponse(BaseModel):
    """Response after password change."""
    
    message: str = "Password changed successfully"
```

---

## Required Dependency

Add `email-validator` to `requirements.txt` for `EmailStr` support:

```
email-validator>=2.0.0
```

---

## Schema Usage Map

| Endpoint | Request Schema | Response Schema |
|----------|---------------|-----------------|
| `POST /api/auth/register` | `ClientRegister` | `ClientRegisterResponse` |
| `POST /api/auth/login` | `ClientLogin` | `TokenResponse` |
| `POST /api/auth/refresh` | `TokenRefreshRequest` | `TokenRefreshResponse` |
| `POST /api/auth/logout` | `LogoutRequest` | `LogoutResponse` |
| `POST /api/auth/forgot-password` | `ForgotPasswordRequest` | `ForgotPasswordResponse` |
| `POST /api/auth/reset-password` | `ResetPasswordRequest` | `ResetPasswordResponse` |
| `GET /api/auth/me` | — (JWT in header) | `ClientProfile` |
| `POST /api/auth/change-password` | `ChangePasswordRequest` | `ChangePasswordResponse` |
| Any auth error | — | `AuthError` |

---

**End of Schemas Document**
