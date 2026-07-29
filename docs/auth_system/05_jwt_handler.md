# 🔑 JWT Handler — Token Management

> Access token creation, validation, and refresh token generation

---

## Overview

This module handles all JWT operations using **HS256** (symmetric) with `python-jose`.

Place this file at: `backend/app/authentication/jwt_handler.py`

---

## Required Dependencies

```
python-jose[cryptography]>=3.3.0
```

---

## File: `app/authentication/jwt_handler.py`

```python
"""
JWT handler — token creation and validation.
Place this file at: backend/app/authentication/jwt_handler.py

Uses HS256 symmetric signing.
Access tokens: 30-minute expiry, carry user claims.
Refresh tokens: opaque random strings stored as hashes in DB.
"""

import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from uuid import uuid4

from jose import jwt, JWTError, ExpiredSignatureError
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# ACCESS TOKEN (JWT)
# ============================================================

def create_access_token(
    client_id: int,
    role: str,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a short-lived JWT access token.
    
    Claims:
        sub: client ID (as string)
        role: client role
        iat: issued at
        exp: expiration
        jti: unique token ID
    
    Args:
        client_id: The client's database ID
        role: Client role ('client', 'admin', 'super_admin')
        extra_claims: Optional additional claims to include
    
    Returns:
        Encoded JWT string
    """
    now = datetime.now(timezone.utc)
    
    payload = {
        "sub": str(client_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": str(uuid4()),  # Unique token ID for revocation tracking
        "type": "access",
    }
    
    if extra_claims:
        payload.update(extra_claims)
    
    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    
    return token


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT access token.
    
    Validates:
        - Signature (HS256)
        - Expiration (exp claim)
        - Token type (must be 'access')
    
    Args:
        token: The JWT string from Authorization header
    
    Returns:
        Decoded payload dictionary
    
    Raises:
        HTTPException 401 if token is invalid/expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        
        # Verify token type
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify required claims
        if not payload.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing subject claim",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return payload
    
    except ExpiredSignatureError:
        logger.debug("Access token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ============================================================
# REFRESH TOKEN (Opaque)
# ============================================================

def create_refresh_token_value() -> str:
    """
    Generate a cryptographically secure random refresh token.
    
    This is NOT a JWT — it's an opaque string.
    The hash of this value is stored in the database.
    The raw value is returned to the client.
    
    Returns:
        64-character URL-safe random string
    """
    return secrets.token_urlsafe(48)  # 48 bytes → 64 chars base64


# ============================================================
# UTILITIES
# ============================================================

def extract_client_id_from_token(token: str) -> int:
    """
    Quick extraction of client_id from a valid access token.
    
    Args:
        token: Valid JWT access token
    
    Returns:
        Client ID as integer
    """
    payload = decode_access_token(token)
    return int(payload["sub"])


def extract_role_from_token(token: str) -> str:
    """
    Quick extraction of role from a valid access token.
    
    Args:
        token: Valid JWT access token
    
    Returns:
        Role string
    """
    payload = decode_access_token(token)
    return payload.get("role", "client")
```

---

## Token Architecture

```
┌──────────────────────────────────────────────────────┐
│                   ACCESS TOKEN (JWT)                  │
├──────────────────────────────────────────────────────┤
│ Format:    eyJhbGciOiJIUzI1NiJ9.eyJz...             │
│ Algorithm: HS256                                      │
│ Expiry:    30 minutes                                 │
│ Storage:   Client-side only (never in DB)             │
│ Contains:  sub, role, iat, exp, jti, type             │
│ Purpose:   Authenticate API requests                  │
└──────────────────────────────────────────────────────┘
                        │
                        │  expired?
                        ▼
┌──────────────────────────────────────────────────────┐
│                  REFRESH TOKEN (Opaque)               │
├──────────────────────────────────────────────────────┤
│ Format:    Random URL-safe base64 (64 chars)          │
│ Expiry:    7 days                                     │
│ Storage:   SHA-256 hash stored in DB                  │
│ Contains:  Nothing (opaque string)                    │
│ Purpose:   Get new access token without re-login      │
└──────────────────────────────────────────────────────┘
```

---

## JWT Payload Example

```json
{
  "sub": "42",
  "role": "client",
  "iat": 1718700000,
  "exp": 1718701800,
  "jti": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "type": "access"
}
```

---

## Security Notes

| Feature | Implementation |
|---------|---------------|
| Secret key | 64-char hex from `JWT_SECRET_KEY` env var |
| Algorithm | HS256 (sufficient for single-service architecture) |
| Token ID (jti) | UUID4 — enables per-token revocation if needed |
| Refresh tokens | Opaque, SHA-256 hashed in DB, never logged |
| Token type claim | Prevents access/refresh token confusion attacks |

---

**End of JWT Handler Document**
