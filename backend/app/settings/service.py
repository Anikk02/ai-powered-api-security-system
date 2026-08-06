import secrets
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.db.models.client import Client
from app.db.models.email_change_token import EmailChangeToken
from app.db.models.refresh_token import RefreshToken
from app.authentication.password_handler import verify_password, hash_password
from app.core.config import settings
from app.utils.email import send_email_change_email

logger = logging.getLogger(__name__)

# ============================================================
# HELPERS
# ============================================================

def _hash_token(token: str) -> str:
    """Hash a token for storage (SHA-256)."""
    return hashlib.sha256(token.encode()).hexdigest()

def _utc_now_naive() -> datetime:
    """Return current UTC datetime as timezone-naive."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

async def _get_client_by_id(db: AsyncSession, client_id: int) -> Optional[Client]:
    """Fetch a client by ID."""
    result = await db.execute(
        select(Client).where(Client.id == client_id)
    )
    return result.scalar_one_or_none()

async def _get_client_by_email(db: AsyncSession, email: str) -> Optional[Client]:
    """Fetch a client by email."""
    result = await db.execute(
        select(Client).where(Client.email == email.lower().strip())
    )
    return result.scalar_one_or_none()

# ============================================================
# PROFILE SERVICE
# ============================================================

async def get_profile(db: AsyncSession, client_id: int) -> Client:
    """Get client profile."""
    client = await _get_client_by_id(db, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    return client

async def update_profile(
    db: AsyncSession, 
    client_id: int, 
    profile_data: dict
) -> Client:
    """Update client profile."""
    client = await _get_client_by_id(db, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )

    update_data = {}
    # Only update company_name since we don't have full_name in the database
    if "company_name" in profile_data and profile_data["company_name"] is not None:
        update_data["company_name"] = profile_data["company_name"]

    if update_data:
        update_data["updated_at"] = _utc_now_naive()
        await db.execute(
            update(Client)
            .where(Client.id == client_id)
            .values(**update_data)
        )
        await db.commit()
        await db.refresh(client)

    return client

# ============================================================
# PASSWORD SERVICE
# ============================================================

async def change_password(
    db: AsyncSession,
    client_id: int,
    current_password: str,
    new_password: str
) -> bool:
    """Change client password."""
    client = await _get_client_by_id(db, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )

    # Verify current password
    if not verify_password(current_password, client.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )

    # Hash new password
    new_password_hash = hash_password(new_password)

    # Update password
    await db.execute(
        update(Client)
        .where(Client.id == client_id)
        .values(
            password_hash=new_password_hash,
            updated_at=_utc_now_naive()
        )
    )
    await db.commit()

    logger.info(f"Password changed for client_id={client_id}")
    return True

# ============================================================
# EMAIL CHANGE SERVICE
# ============================================================

async def request_email_change(
    db: AsyncSession,
    client_id: int,
    new_email: str
) -> str:
    """Request email change and send verification email."""
    client = await _get_client_by_id(db, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )

    # Check if new email is same as current
    if client.email == new_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New email is same as current email"
        )

    # Check if new email is already in use
    existing_client = await _get_client_by_email(db, new_email)
    if existing_client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already in use"
        )

    # Generate token
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    now = _utc_now_naive()

    # Invalidate existing tokens for this client
    await db.execute(
        update(EmailChangeToken)
        .where(
            EmailChangeToken.client_id == client_id,
            EmailChangeToken.used == False
        )
        .values(
            used=True, 
            used_at=now
        )
    )

    # Create new token
    email_change_token = EmailChangeToken(
        client_id=client_id,
        new_email=new_email,
        token_hash=token_hash,
        expires_at=now + timedelta(hours=24),
        used=False,
        created_at=now
    )
    db.add(email_change_token)
    await db.commit()

    # Build verification link
    verification_link = f"{settings.FRONTEND_URL}/confirm-email?token={raw_token}"

    # Send verification email using the existing email utility
    send_email_change_email(new_email, verification_link)

    logger.info(f"Email change requested for client_id={client_id}: {client.email} → {new_email}")

    return verification_link

async def confirm_email_change(
    db: AsyncSession,
    token: str
) -> str:
    """Confirm email change with token."""
    token_hash = _hash_token(token)
    now = _utc_now_naive()

    # Find token record
    result = await db.execute(
        select(EmailChangeToken).where(
            EmailChangeToken.token_hash == token_hash,
            EmailChangeToken.used == False
        )
    )
    email_change_token = result.scalar_one_or_none()

    if not email_change_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token"
        )

    # Check if token is expired
    if email_change_token.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token has expired"
        )

    # Check if new email is still available
    existing_client = await _get_client_by_email(db, email_change_token.new_email)
    if existing_client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already in use"
        )

    # Update client email
    await db.execute(
        update(Client)
        .where(Client.id == email_change_token.client_id)
        .values(
            email=email_change_token.new_email,
            updated_at=now
        )
    )

    # Mark token as used
    email_change_token.used = True
    email_change_token.used_at = now
    await db.commit()

    logger.info(f"Email confirmed for client_id={email_change_token.client_id}")

    return "Email changed successfully"

# ============================================================
# ACCOUNT DELETION SERVICE
# ============================================================

async def delete_account(
    db: AsyncSession,
    client_id: int,
    password: str
) -> bool:
    """Delete client account (soft delete)."""
    client = await _get_client_by_id(db, client_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )

    # Verify password
    if not verify_password(password, client.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password is incorrect"
        )

    # Soft delete - set status to deleted
    await db.execute(
        update(Client)
        .where(Client.id == client_id)
        .values(
            status="deleted",
            updated_at=_utc_now_naive()
        )
    )
    await db.commit()

    logger.warning(f"Account deleted for client_id={client_id}")

    return True

# ============================================================
# PLAN SERVICE
# ============================================================

async def get_plan_info(db: AsyncSession, client_id: int) -> dict:
    """Get current plan information."""
    # For now, return a default plan
    # This can be extended with actual subscription logic
    return {
        "name": "Growth",
        "next_renewal": datetime.now(timezone.utc) + timedelta(days=30)
    }

# ============================================================
# LOGOUT SERVICE
# ============================================================

async def logout_all_devices(
    db: AsyncSession,
    client_id: int
) -> bool:
    """Revoke all refresh tokens for a client."""
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.client_id == client_id,
            RefreshToken.revoked == False
        )
        .values(
            revoked=True,
            revoked_at=_utc_now_naive()
        )
    )
    await db.commit()
    
    logger.info(f"All sessions revoked for client_id={client_id}")
    return True