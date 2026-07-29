# 🛡️ Security Hardening — Production Checklist

> Rate limiting, brute-force protection, CORS, and OWASP best practices

---

## Overview

This document covers security measures for the JWT authentication system,
following **OWASP Authentication Cheat Sheet** recommendations tuned for 400–500 users.

---

## 1. Brute-Force Protection (Built into Auth Service)

The auth service already includes brute-force protection:

```python
# Already implemented in 04_auth_service.md → login_client()

MAX_FAILED_ATTEMPTS = 10        # Lock after 10 failures
LOCKOUT_DURATION_MINUTES = 30   # Lock for 30 minutes
```

### How It Works

```
Login attempt
    │
    ├── Password correct?
    │   ├── YES → Reset failed_login_attempts to 0, unlock
    │   └── NO  → Increment failed_login_attempts
    │             │
    │             ├── < 10 failures → Return "Invalid credentials"
    │             └── ≥ 10 failures → Lock account for 30 min
    │                                  Status → "locked"
    │
    └── Account locked?
        ├── YES → Return 423 Locked with remaining time
        └── NO  → Continue authentication
```

---

## 2. Login Rate Limiting (IP-Based)

Add a rate limiter middleware for login attempts per IP:

### File: `app/authentication/rate_limiter.py`

```python
"""
IP-based rate limiting for login endpoint.
Place this file at: backend/app/authentication/rate_limiter.py

Limits: 5 login attempts per 15 minutes per IP address.
Uses Redis for distributed rate limiting.
"""

import time
import logging
from fastapi import Request, HTTPException, status
from app.state.redis_client import redis_client  # Use existing Redis

logger = logging.getLogger(__name__)

# Configuration
LOGIN_RATE_LIMIT = 5          # Max attempts
LOGIN_RATE_WINDOW = 900       # 15 minutes in seconds
LOGIN_RATE_PREFIX = "auth:login:rate:"


async def check_login_rate_limit(request: Request) -> None:
    """
    Check if the IP has exceeded login rate limit.
    
    Call this at the start of the login endpoint.
    
    Raises:
        HTTPException 429 if rate limit exceeded
    """
    client_ip = request.client.host if request.client else "unknown"
    key = f"{LOGIN_RATE_PREFIX}{client_ip}"
    
    try:
        # Get current count
        current = await redis_client.get(key)
        
        if current and int(current) >= LOGIN_RATE_LIMIT:
            ttl = await redis_client.ttl(key)
            logger.warning(
                f"Login rate limit exceeded for IP: {client_ip}"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many login attempts. Try again in {ttl} seconds.",
                headers={"Retry-After": str(ttl)},
            )
        
        # Increment counter
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, LOGIN_RATE_WINDOW)
        await pipe.execute()
        
    except HTTPException:
        raise
    except Exception as e:
        # If Redis is down, allow the request (fail-open)
        logger.error(f"Rate limiter error: {e}")


async def reset_login_rate_limit(request: Request) -> None:
    """
    Reset rate limit on successful login.
    """
    client_ip = request.client.host if request.client else "unknown"
    key = f"{LOGIN_RATE_PREFIX}{client_ip}"
    
    try:
        await redis_client.delete(key)
    except Exception:
        pass  # Non-critical
```

### Usage in Login Route

```python
# In 07_auth_routes.md → login endpoint, add:

from app.authentication.rate_limiter import check_login_rate_limit

@router.post("/login", response_model=TokenResponse)
async def login(
    data: ClientLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Check rate limit BEFORE processing
    await check_login_rate_limit(request)
    
    # ... rest of login logic ...
```

---

## 3. Password Security

### 3.1 Password Requirements (Already in Schemas)

| Rule | Value |
|------|-------|
| Minimum length | 8 characters |
| Maximum length | 128 characters |
| Uppercase required | ≥ 1 character |
| Lowercase required | ≥ 1 character |
| Digit required | ≥ 1 digit |

### 3.2 Additional Recommendations

```python
# Optional: Add these checks to the password validator

# Check against common passwords list
COMMON_PASSWORDS = {
    "password", "12345678", "qwerty123", "password1",
    "admin123", "letmein12", "welcome1", "monkey123",
}

@field_validator("password")
@classmethod
def validate_password_strength(cls, v: str) -> str:
    # ... existing checks ...
    
    if v.lower() in COMMON_PASSWORDS:
        raise ValueError("Password is too common")
    
    return v
```

---

## 4. JWT Security Best Practices

### 4.1 Token Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| Algorithm | HS256 | Sufficient for single-service |
| Access token expiry | 30 minutes | Short-lived = low risk if stolen |
| Refresh token expiry | 7 days | Balance security vs UX |
| Secret key | 64-char hex | Cryptographically random |
| Token type claim | ✅ Included | Prevents token confusion attacks |
| JTI (token ID) | ✅ Included | Enables per-token revocation |

### 4.2 Token Storage Recommendations (Client-Side)

```
Frontend Storage:
┌─────────────────────────────────────────────────────┐
│                                                       │
│  Access Token:  Store in memory (JavaScript variable)│
│                 ❌ NOT in localStorage                │
│                 ❌ NOT in cookies                     │
│                                                       │
│  Refresh Token: Store in httpOnly secure cookie      │
│                 OR in memory if SPA                   │
│                                                       │
└─────────────────────────────────────────────────────┘
```

### 4.3 Response Headers

```python
# Add security headers to auth responses
# In middleware or response hook:

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Cache-Control": "no-store",  # Never cache auth responses
    "Pragma": "no-cache",
}
```

---

## 5. CORS Configuration for Auth

```python
# Update ALLOWED_ORIGINS in config.py for production

# Development
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
]

# Production
ALLOWED_ORIGINS = [
    "https://dashboard.triansec.com",
    "https://app.triansec.com",
]
```

Middleware configuration:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,     # Required for cookies
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Request-ID"],
)
```

---

## 6. Refresh Token Rotation (Optional Enhancement)

For maximum security, rotate refresh tokens on every use:

```python
async def refresh_with_rotation(
    db: AsyncSession,
    data: TokenRefreshRequest,
) -> TokenResponse:
    """
    Refresh with token rotation:
    1. Validate old refresh token
    2. Revoke old refresh token
    3. Issue new refresh token
    4. Issue new access token
    """
    # Validate existing token
    token_hash = _hash_token(data.refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash
        )
    )
    old_token = result.scalar_one_or_none()
    
    if not old_token or not old_token.is_valid:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    # Revoke old token
    old_token.revoked = True
    old_token.revoked_at = datetime.now(timezone.utc)
    
    # Generate new token pair
    client = await _get_client_by_id(db, old_token.client_id)
    
    new_access = create_access_token(client.id, client.role)
    new_refresh_raw = create_refresh_token_value()
    new_refresh_hash = _hash_token(new_refresh_raw)
    
    # Store new refresh token
    new_token = RefreshToken(
        client_id=client.id,
        token_hash=new_refresh_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(new_token)
    await db.commit()
    
    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh_raw,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
```

---

## 7. Token Cleanup Background Job

```python
"""
Background job to clean up expired tokens.
Run daily via scheduler or cron.
"""

async def cleanup_expired_tokens():
    """Remove expired and revoked tokens."""
    async with AsyncSessionLocal() as session:
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)
        
        # Cleanup expired refresh tokens
        result = await session.execute(
            text("""
                DELETE FROM refresh_tokens 
                WHERE (expires_at < :now AND revoked = FALSE)
                   OR (revoked = TRUE AND revoked_at < :cutoff)
            """),
            {"now": now, "cutoff": thirty_days_ago}
        )
        refresh_deleted = result.rowcount
        
        # Cleanup password reset tokens
        result = await session.execute(
            text("""
                DELETE FROM password_reset_tokens 
                WHERE expires_at < :now
                   OR (used = TRUE AND used_at < :cutoff)
            """),
            {"now": now, "cutoff": now - timedelta(days=7)}
        )
        reset_deleted = result.rowcount
        
        await session.commit()
    
    logger.info(
        f"Token cleanup: {refresh_deleted} refresh tokens, "
        f"{reset_deleted} reset tokens removed"
    )
```

---

## 8. Security Checklist

| # | Check | Status | Notes |
|---|-------|:------:|-------|
| 1 | Passwords hashed with bcrypt (12 rounds) | ✅ | 06_password_handler.md |
| 2 | JWT secret key ≥ 256 bits | ✅ | 64-char hex = 256 bits |
| 3 | Short-lived access tokens (≤ 30 min) | ✅ | 30 minutes |
| 4 | Refresh tokens stored as hashes | ✅ | SHA-256 in DB |
| 5 | Password reset tokens single-use | ✅ | `used` flag |
| 6 | Password reset tokens short-lived (≤ 15 min) | ✅ | 15 minutes |
| 7 | Account lockout after failed attempts | ✅ | 10 attempts → 30 min lock |
| 8 | Login rate limiting (IP-based) | ✅ | 5 per 15 min via Redis |
| 9 | Generic error messages (don't leak info) | ✅ | "Invalid email or password" |
| 10 | HTTPS in production | 🔧 | Configure via nginx/reverse proxy |
| 11 | Secure CORS config | ✅ | Whitelist specific origins |
| 12 | No caching of auth responses | ✅ | `Cache-Control: no-store` |
| 13 | Logout revokes tokens | ✅ | Refresh tokens revoked in DB |
| 14 | Password reset revokes all sessions | ✅ | All refresh tokens revoked |
| 15 | Token type validation | ✅ | `type: "access"` claim |

---

**End of Security Hardening Document**
