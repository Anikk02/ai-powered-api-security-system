import secrets
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.utils.email import send_password_reset_email, send_email_change_email

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.db.models.client import Client
from app.db.models.refresh_token import RefreshToken
from app.db.models.email_change_token import EmailChangeToken
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
    ChangeEmailRequest,
    ChangeEmailResponse,
    ChangeEmailConfirmRequest,
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
        if client.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
            client.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=settings.ACCOUNT_LOCKOUT_MINUTES
            )
            client.status = "locked"
            logger.warning(
                f"Account locked due to {settings.MAX_FAILED_LOGIN_ATTEMPTS} "
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
    4. Return reset link (dev) or send email (prod)
    """

    client = await _get_client_by_email(db, data.email)

    # Always return success (avoid user enumeration)
    if not client:
        return ForgotPasswordResponse(
            message="If the email exists, a reset link has been sent"
        )

    # 🔐 Generate token
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)

    # ❌ Invalidate existing tokens
    await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.client_id == client.id,
            PasswordResetToken.used == False,
        )
        .values(
            used=True,
            used_at=datetime.now(timezone.utc)
        )
    )

    # 💾 Store new token
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

    # 🔗 Build frontend reset link
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"

    # 📧 Send email (dev: logs link; prod: sends via SMTP)
    send_password_reset_email(client.email, reset_link)

    # 📦 Response
    response = ForgotPasswordResponse(
        message="If the email exists, a reset link has been sent"
    )

    # 🚧 DEV MODE ONLY → expose link in response body
    if settings.ENVIRONMENT.value == "development":
        response.reset_link = reset_link

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
    """

    # 1️⃣ Hash incoming token (never compare raw tokens)
    token_hash = _hash_token(data.token)

    # 2️⃣ Fetch token record
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

    # 3️⃣ Validate token (expiry + usage)
    if not token_record.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired or already been used"
        )

    # 4️⃣ Fetch client
    client = await _get_client_by_id(db, token_record.client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )

    # 5️⃣ Hash new password
    new_hash = hash_password(data.new_password)

    # 🚫 OPTIONAL (recommended): prevent same password reuse
    if verify_password(data.new_password, client.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from old password"
        )

    # 6️⃣ Update client security state
    client.password_hash = new_hash
    client.failed_login_attempts = 0
    client.locked_until = None

    if client.status == "locked":
        client.status = "active"

    # 7️⃣ Mark token as used
    token_record.used = True
    token_record.used_at = datetime.now(timezone.utc)

    # 8️⃣ Revoke all refresh tokens (force logout everywhere)
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

    # 9️⃣ Commit everything
    await db.commit()

    logger.info(f"Password reset completed for: {client.email}")
    logger.warning(f"SECURITY: All sessions revoked for {client.email}")

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


#  ---- EMAIL CHANGE REQUEST ---- #
async def request_email_change(
    db: AsyncSession,
    client: Client,
    data: ChangeEmailRequest,
) -> ChangeEmailResponse:

    # ❌ Prevent same email
    if client.email == data.new_email:
        raise HTTPException(400, "New email must be different")

    # ❌ Check if email already exists
    existing = await _get_client_by_email(db, data.new_email)
    if existing:
        raise HTTPException(400, "Email already in use")

    # 🔐 Generate token
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)

    # ❌ Invalidate old tokens
    await db.execute(
        update(EmailChangeToken)
        .where(
            EmailChangeToken.client_id == client.id,
            EmailChangeToken.used == False
        )
        .values(used=True, used_at=datetime.now(timezone.utc))
    )

    # 💾 Store new token
    record = EmailChangeToken(
        client_id=client.id,
        new_email=data.new_email,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )

    db.add(record)
    await db.commit()

    # 🔗 Build link
    link = f"{settings.FRONTEND_URL}/confirm-email?token={raw_token}"

    logger.info(f"Email change requested: {client.email} → {data.new_email}")

    # 📧 Send verification email to the NEW address
    send_email_change_email(data.new_email, link)

    response = ChangeEmailResponse(
        message="Verification link sent to new email"
    )

    # 🚧 DEV MODE ONLY → expose link in response body
    if settings.ENVIRONMENT.value == "development":
        response.verification_link = link

    return response


# ---- CONFIRM EMAIL CHANGE ---- #

async def confirm_email_change(
    db: AsyncSession,
    data: ChangeEmailConfirmRequest,
) -> ChangeEmailResponse:

    # 1️⃣ Hash token
    token_hash = _hash_token(data.token)

    # 2️⃣ Fetch record
    result = await db.execute(
        select(EmailChangeToken).where(
            EmailChangeToken.token_hash == token_hash
        )
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(400, "Invalid or expired token")

    # 3️⃣ Validate
    if record.used or record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(400, "Token expired or already used")

    # 4️⃣ Fetch client
    client = await _get_client_by_id(db, record.client_id)
    if not client:
        raise HTTPException(404, "Client not found")

    # 5️⃣ Update email
    old_email = client.email
    client.email = record.new_email

    # 6️⃣ Mark token used
    record.used = True
    record.used_at = datetime.now(timezone.utc)

    await db.commit()

    logger.info(f"Email changed: {old_email} → {client.email}")

    return ChangeEmailResponse(
        message="Email updated successfully"
    )
