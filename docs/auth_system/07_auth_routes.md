# 🌐 Auth Routes — FastAPI Endpoints

> All authentication API endpoints

---

## Overview

FastAPI router with 8 endpoints covering the full auth lifecycle.
Place this file at: `backend/app/authentication/routes.py`

---

## File: `app/authentication/routes.py`

```python
"""
Authentication routes — FastAPI endpoints.
Place this file at: backend/app/authentication/routes.py

Endpoints:
    POST /api/auth/register         - Client registration
    POST /api/auth/login            - Login + get tokens
    POST /api/auth/refresh          - Refresh access token
    POST /api/auth/logout           - Revoke refresh token
    POST /api/auth/logout-all       - Revoke all sessions
    POST /api/auth/forgot-password  - Request password reset
    POST /api/auth/reset-password   - Reset password with token
    GET  /api/auth/me               - Get current user profile
    POST /api/auth/change-password  - Change password (authenticated)
"""

import logging
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth import (
    ClientRegister,
    ClientRegisterResponse,
    ClientLogin,
    TokenResponse,
    TokenRefreshRequest,
    TokenRefreshResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    LogoutRequest,
    LogoutResponse,
    ClientProfile,
    ChangePasswordRequest,
    ChangePasswordResponse,
    AuthError,
)
from app.authentication.service import (
    register_client,
    login_client,
    refresh_access_token,
    forgot_password,
    reset_password,
    logout_client,
    logout_all_devices,
)
from app.authentication.dependencies import (
    get_current_client,
    require_active_client,
)
from app.authentication.password_handler import (
    verify_password,
    hash_password,
)
from app.db.models.client import Client

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
    responses={
        401: {"model": AuthError, "description": "Unauthorized"},
        403: {"model": AuthError, "description": "Forbidden"},
    },
)


# ============================================================
# 1. REGISTER
# ============================================================

@router.post(
    "/register",
    response_model=ClientRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new client",
    description="Create a new client account with email and password.",
)
async def register(
    data: ClientRegister,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new client.
    
    - **email**: Valid email address (must be unique)
    - **password**: Min 8 chars, requires uppercase, lowercase, and digit
    - **company_name**: Optional company or organization name
    """
    return await register_client(db, data)


# ============================================================
# 2. LOGIN
# ============================================================

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and get tokens",
    description="Authenticate with email/password and receive JWT access + refresh tokens.",
)
async def login(
    data: ClientLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Login with email and password.
    
    Returns:
    - **access_token**: JWT valid for 30 minutes
    - **refresh_token**: Opaque token valid for 7 days
    - **expires_in**: Access token expiry in seconds
    """
    # Extract client info for session tracking
    ip_address = request.client.host if request.client else None
    device_info = request.headers.get("User-Agent", "")[:500]
    
    return await login_client(
        db, data,
        ip_address=ip_address,
        device_info=device_info,
    )


# ============================================================
# 3. REFRESH TOKEN
# ============================================================

@router.post(
    "/refresh",
    response_model=TokenRefreshResponse,
    summary="Refresh access token",
    description="Get a new access token using a valid refresh token.",
)
async def refresh(
    data: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh an expired access token.
    
    Send the refresh_token received during login.
    Returns a new access_token (the refresh_token stays the same).
    """
    return await refresh_access_token(db, data)


# ============================================================
# 4. LOGOUT
# ============================================================

@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Logout (revoke refresh token)",
    description="Revoke the refresh token to end the session.",
)
async def logout(
    data: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(get_current_client),
):
    """
    Logout by revoking the provided refresh token.
    
    Requires a valid access token in the Authorization header.
    """
    return await logout_client(db, data)


# ============================================================
# 5. LOGOUT ALL DEVICES
# ============================================================

@router.post(
    "/logout-all",
    response_model=LogoutResponse,
    summary="Logout from all devices",
    description="Revoke all refresh tokens for the current client.",
)
async def logout_all(
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(require_active_client),
):
    """
    Logout from all devices by revoking all refresh tokens.
    
    After this, the client must login again on every device.
    """
    return await logout_all_devices(db, current_client.id)


# ============================================================
# 6. FORGOT PASSWORD
# ============================================================

@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Request password reset",
    description="Send a password reset token for the given email.",
)
async def forgot_pw(
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Request a password reset.
    
    - Always returns success (doesn't reveal if email exists)
    - In development mode, the reset token is included in the response
    - In production, the token would be sent via email
    """
    return await forgot_password(db, data)


# ============================================================
# 7. RESET PASSWORD
# ============================================================

@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    summary="Reset password with token",
    description="Set a new password using a valid reset token.",
)
async def reset_pw(
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Reset password using the token from forgot-password.
    
    - Token is single-use and expires in 15 minutes
    - All existing sessions are revoked after reset
    """
    return await reset_password(db, data)


# ============================================================
# 8. GET CURRENT USER
# ============================================================

@router.get(
    "/me",
    response_model=ClientProfile,
    summary="Get current user profile",
    description="Returns the profile of the currently authenticated client.",
)
async def get_me(
    current_client: Client = Depends(require_active_client),
):
    """
    Get the current authenticated client's profile.
    
    Requires a valid access token in the Authorization header:
    `Authorization: Bearer <access_token>`
    """
    return ClientProfile.model_validate(current_client)


# ============================================================
# 9. CHANGE PASSWORD (Authenticated)
# ============================================================

@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
    summary="Change password",
    description="Change password while logged in (requires current password).",
)
async def change_pw(
    data: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_client: Client = Depends(require_active_client),
):
    """
    Change password while logged in.
    
    - Must provide current password for verification
    - New password must meet complexity requirements
    """
    from fastapi import HTTPException
    
    # Verify current password
    if not verify_password(data.current_password, current_client.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # Hash and update
    current_client.password_hash = hash_password(data.new_password)
    await db.commit()
    
    logger.info(f"Password changed for client: {current_client.email}")
    
    return ChangePasswordResponse(message="Password changed successfully")
```

---

## Router Registration

Add this to your existing `main.py`:

```python
# In backend/app/main.py — add this import and include
from app.authentication.routes import router as auth_router

app.include_router(auth_router)
```

---

## Endpoint Reference

| # | Method | Endpoint | Auth | Request Body | Response |
|---|--------|----------|:----:|-------------|----------|
| 1 | POST | `/api/auth/register` | ❌ | `ClientRegister` | `201` + `ClientRegisterResponse` |
| 2 | POST | `/api/auth/login` | ❌ | `ClientLogin` | `200` + `TokenResponse` |
| 3 | POST | `/api/auth/refresh` | ❌ | `TokenRefreshRequest` | `200` + `TokenRefreshResponse` |
| 4 | POST | `/api/auth/logout` | ✅ | `LogoutRequest` | `200` + `LogoutResponse` |
| 5 | POST | `/api/auth/logout-all` | ✅ | — | `200` + `LogoutResponse` |
| 6 | POST | `/api/auth/forgot-password` | ❌ | `ForgotPasswordRequest` | `200` + `ForgotPasswordResponse` |
| 7 | POST | `/api/auth/reset-password` | ❌ | `ResetPasswordRequest` | `200` + `ResetPasswordResponse` |
| 8 | GET | `/api/auth/me` | ✅ | — | `200` + `ClientProfile` |
| 9 | POST | `/api/auth/change-password` | ✅ | `ChangePasswordRequest` | `200` + `ChangePasswordResponse` |

---

## Error Responses

All endpoints return standard error format:

```json
{
    "detail": "Error message here"
}
```

| Status Code | Meaning |
|:-----------:|---------|
| `400` | Bad request (invalid data) |
| `401` | Unauthorized (bad credentials / expired token) |
| `403` | Forbidden (suspended account) |
| `409` | Conflict (email already registered) |
| `422` | Validation error (Pydantic) |
| `423` | Locked (too many failed attempts) |

---

**End of Auth Routes Document**
