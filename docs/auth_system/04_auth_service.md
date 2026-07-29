# 🔐 Auth Service — Core Business Logic

> Registration, login, token refresh, password reset, and logout

---

## Overview

This is the **central service layer** that orchestrates all authentication operations.
It uses the models, schemas, JWT handler, and password handler.

Place this file at: `backend/app/authentication/service.py`

---

## File: `app/authentication/service.py`

```python
"""
Authentication service — core business logic.
Place this file at: backend/app/authentication/service.py

Handles: register, login, refresh, forgot-password, reset-password, logout
"""

import secrets
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.db.models.client import Client
from app.db.models.refresh_token import RefreshToken
from app.db.models.password_reset_token import PasswordResetToken
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
)
from app.authentication.jwt_handler import (
    create_access_token,
    create_refresh_token_value,
)
from app.authentication.password_handler import hash_password, verify_password
from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# HELPERS
# ============================================================

def _hash_token(token: str) -> str:
    """Hash a token for storage (SHA-256)."""
    return hashlib.sha256(token.encode()).hexdigest()


async def _get_client_by_email(
    db: AsyncSession, email: str
) -> Optional[Client]:
    """Fetch a client by email address."""
    result = await db.execute(
        select(Client).where(Client.email == email.lower().strip())
    )
    return result.scalar_one_or_none()


async def _get_client_by_id(
    db: AsyncSession, client_id: int
) -> Optional[Client]:
    """Fetch a client by ID."""
    result = await db.execute(
        select(Client).where(Client.id == client_id)
    )
    return result.scalar_one_or_none()


# ============================================================
# 1. REGISTRATION
# ============================================================

async def register_client(
    db: AsyncSession,
    data: ClientRegister
) -> ClientRegisterResponse:
    """
    Register a new client.
    
    Flow:
    1. Check if email already exists
    2. Hash password
    3. Create client record
    4. Return client info
    """
    # 1. Check duplicate email
    existing = await _get_client_by_email(db, data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )
    
    # 2. Hash password
    hashed = hash_password(data.password)
    
    # 3. Create client
    client = Client(
        email=data.email.lower().strip(),
        password_hash=hashed,
        company_name=data.company_name,
        role="client",
        status="active",
        email_verified=False,
    )
    
    db.add(client)
    await db.commit()
    await db.refresh(client)
    
    logger.info(f"New client registered: {client.email} (id={client.id})")
    
    # 4. Return response
    return ClientRegisterResponse(
        id=client.id,
        email=client.email,
        company_name=client.company_name,
        role=client.role,
        status=client.status,
        message="Registration successful",
    )


# ============================================================
# 2. LOGIN
# ============================================================

MAX_FAILED_ATTEMPTS = 10
LOCKOUT_DURATION_MINUTES = 30

async def login_client(
    db: AsyncSession,
    data: ClientLogin,
    ip_address: Optional[str] = None,
    device_info: Optional[str] = None,
) -> TokenResponse:
    """
    Authenticate a client and return JWT token pair.
    
    Flow:
    1. Find client by email
    2. Check account status (active, not locked)
    3. Verify password
    4. Generate access + refresh tokens
    5. Store refresh token hash in DB
    6. Update last_login_at
    7. Return token pair
    """
    # 1. Find client
    client = await _get_client_by_email(db, data.email)
    if not client:
        # Don't reveal whether email exists
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # 2. Check account status
    if client.status == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account suspended. Contact support."
        )
    
    if client.is_locked:
        remaining = (client.locked_until - datetime.now(timezone.utc)).seconds
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked. Try again in {remaining // 60} minutes."
        )
    
    # 3. Verify password
    if not verify_password(data.password, client.password_hash):
        # Increment failed attempts
        client.failed_login_attempts += 1
        
        # Lock account if too many failures
        if client.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            client.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=LOCKOUT_DURATION_MINUTES
            )
            client.status = "locked"
            logger.warning(
                f"Account locked due to {MAX_FAILED_ATTEMPTS} "
                f"failed attempts: {client.email}"
            )
        
        await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Reset failed attempts on successful login
    client.failed_login_attempts = 0
    client.locked_until = None
    if client.status == "locked":
        client.status = "active"
    
    # 4. Generate tokens
    access_token = create_access_token(
        client_id=client.id,
        role=client.role,
    )
    
    raw_refresh_token = create_refresh_token_value()
    refresh_token_hash = _hash_token(raw_refresh_token)
    
    # 5. Store refresh token in DB
    refresh_token_record = RefreshToken(
        client_id=client.id,
        token_hash=refresh_token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        ),
        device_info=device_info,
        ip_address=ip_address,
    )
    db.add(refresh_token_record)
    
    # 6. Update last login
    client.last_login_at = datetime.now(timezone.utc)
    
    await db.commit()
    
    logger.info(f"Client logged in: {client.email} (id={client.id})")
    
    # 7. Return token pair
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ============================================================
# 3. TOKEN REFRESH
# ============================================================

async def refresh_access_token(
    db: AsyncSession,
    data: TokenRefreshRequest,
) -> TokenRefreshResponse:
    """
    Validate refresh token and issue a new access token.
    
    Flow:
    1. Hash the provided refresh token
    2. Look up in DB
    3. Validate (not expired, not revoked)
    4. Generate new access token
    5. Return new access token
    """
    # 1. Hash the token
    token_hash = _hash_token(data.refresh_token)
    
    # 2. Look up
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash
        )
    )
    token_record = result.scalar_one_or_none()
    
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # 3. Validate
    if not token_record.is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired or revoked"
        )
    
    # 4. Get the client
    client = await _get_client_by_id(db, token_record.client_id)
    if not client or not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account not found or inactive"
        )
    
    # 5. Generate new access token
    new_access_token = create_access_token(
        client_id=client.id,
        role=client.role,
    )
    
    logger.info(f"Token refreshed for client: {client.email}")
    
    return TokenRefreshResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ============================================================
# 4. FORGOT PASSWORD
# ============================================================

async def forgot_password(
    db: AsyncSession,
    data: ForgotPasswordRequest,
) -> ForgotPasswordResponse:
    """
    Generate a password reset token.
    
    Flow:
    1. Find client by email (don't reveal if not found)
    2. Generate random reset token
    3. Store hash in DB
    4. Return token (dev mode) or send email (production)
    """
    client = await _get_client_by_email(db, data.email)
    
    # Always return success (don't reveal if email exists)
    if not client:
        return ForgotPasswordResponse(
            message="If the email exists, a reset link has been sent"
        )
    
    # Generate token
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    
    # Invalidate any existing reset tokens for this client
    await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.client_id == client.id,
            PasswordResetToken.used == False,
        )
        .values(used=True, used_at=datetime.now(timezone.utc))
    )
    
    # Store new reset token
    reset_token = PasswordResetToken(
        client_id=client.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(
            minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES
        ),
    )
    db.add(reset_token)
    await db.commit()
    
    logger.info(f"Password reset requested for: {client.email}")
    
    # In dev mode, return the token directly
    # In production, send via email and don't return it
    response = ForgotPasswordResponse(
        message="If the email exists, a reset link has been sent"
    )
    
    if settings.ENVIRONMENT == "development":
        response.reset_token = raw_token
    
    return response


# ============================================================
# 5. RESET PASSWORD
# ============================================================

async def reset_password(
    db: AsyncSession,
    data: ResetPasswordRequest,
) -> ResetPasswordResponse:
    """
    Reset password using a valid reset token.
    
    Flow:
    1. Hash the provided token
    2. Look up in DB
    3. Validate (not expired, not used)
    4. Hash new password
    5. Update client password
    6. Mark token as used
    7. Revoke all refresh tokens (force re-login)
    """
    # 1. Hash the token
    token_hash = _hash_token(data.token)
    
    # 2. Look up
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash
        )
    )
    token_record = result.scalar_one_or_none()
    
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # 3. Validate
    if not token_record.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired or already been used"
        )
    
    # 4. Hash new password
    new_hash = hash_password(data.new_password)
    
    # 5. Update client password
    client = await _get_client_by_id(db, token_record.client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )
    
    client.password_hash = new_hash
    client.failed_login_attempts = 0
    client.locked_until = None
    if client.status == "locked":
        client.status = "active"
    
    # 6. Mark token as used
    token_record.used = True
    token_record.used_at = datetime.now(timezone.utc)
    
    # 7. Revoke all refresh tokens (security: force re-login)
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.client_id == client.id,
            RefreshToken.revoked == False,
        )
        .values(
            revoked=True,
            revoked_at=datetime.now(timezone.utc),
        )
    )
    
    await db.commit()
    
    logger.info(f"Password reset completed for: {client.email}")
    
    return ResetPasswordResponse(
        message="Password reset successful. Please login with your new password."
    )


# ============================================================
# 6. LOGOUT
# ============================================================

async def logout_client(
    db: AsyncSession,
    data: LogoutRequest,
) -> LogoutResponse:
    """
    Revoke a refresh token (logout from one device).
    
    Flow:
    1. Hash the refresh token
    2. Find and revoke it
    """
    token_hash = _hash_token(data.refresh_token)
    
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash
        )
    )
    token_record = result.scalar_one_or_none()
    
    if token_record and not token_record.revoked:
        token_record.revoked = True
        token_record.revoked_at = datetime.now(timezone.utc)
        await db.commit()
    
    # Always return success (don't reveal token validity)
    return LogoutResponse(message="Logged out successfully")


# ============================================================
# 7. LOGOUT ALL DEVICES
# ============================================================

async def logout_all_devices(
    db: AsyncSession,
    client_id: int,
) -> LogoutResponse:
    """
    Revoke ALL refresh tokens for a client (logout everywhere).
    """
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.client_id == client_id,
            RefreshToken.revoked == False,
        )
        .values(
            revoked=True,
            revoked_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()
    
    logger.info(f"All sessions revoked for client_id={client_id}")
    
    return LogoutResponse(message="Logged out from all devices")
```

---

## Service Function Summary

| Function | Auth Required | DB Writes | Tokens Issued |
|----------|:---:|:---:|:---:|
| `register_client()` | ❌ | 1 INSERT (client) | None |
| `login_client()` | ❌ | 1 INSERT (refresh_token) + UPDATE (client) | Access + Refresh |
| `refresh_access_token()` | ❌ | None | Access only |
| `forgot_password()` | ❌ | 1 INSERT (reset_token) + UPDATE (old tokens) | Reset token |
| `reset_password()` | ❌ | UPDATE (client + reset_token + refresh_tokens) | None |
| `logout_client()` | ✅ | UPDATE (refresh_token) | None |
| `logout_all_devices()` | ✅ | UPDATE (all refresh_tokens) | None |

---

**End of Auth Service Document**
