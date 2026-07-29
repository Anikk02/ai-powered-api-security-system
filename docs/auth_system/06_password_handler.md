# 🔒 Password Handler — Secure Hashing

> bcrypt password hashing and verification

---

## Overview

Minimal, focused module for password operations using **bcrypt** via `passlib`.
Place this file at: `backend/app/authentication/password_handler.py`

---

## Required Dependencies

```
passlib[bcrypt]>=1.7.4
bcrypt>=4.0.0
```

---

## File: `app/authentication/password_handler.py`

```python
"""
Password handler — bcrypt hashing and verification.
Place this file at: backend/app/authentication/password_handler.py

Uses bcrypt with 12 rounds (tuned for 400-500 user scale).
- 12 rounds ≈ 250ms per hash on modern hardware
- Constant-time comparison to prevent timing attacks
"""

from passlib.context import CryptContext

# ============================================================
# CONFIGURATION
# ============================================================

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # 12 rounds: secure + fast enough for 500 users
)


# ============================================================
# PUBLIC API
# ============================================================

def hash_password(plain_password: str) -> str:
    """
    Hash a plaintext password using bcrypt.
    
    Args:
        plain_password: The raw password string
    
    Returns:
        bcrypt hash string (60 characters, starts with $2b$)
    
    Example:
        >>> hash_password("SecurePass123")
        '$2b$12$LJ3m4ys3Lk8nOfQ9.R7GHe...'
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a bcrypt hash.
    
    Uses constant-time comparison to prevent timing attacks.
    
    Args:
        plain_password: The raw password to verify
        hashed_password: The stored bcrypt hash
    
    Returns:
        True if password matches, False otherwise
    
    Example:
        >>> hashed = hash_password("SecurePass123")
        >>> verify_password("SecurePass123", hashed)
        True
        >>> verify_password("WrongPassword", hashed)
        False
    """
    return pwd_context.verify(plain_password, hashed_password)


def needs_rehash(hashed_password: str) -> bool:
    """
    Check if a password hash needs to be upgraded.
    
    This happens when:
    - The bcrypt rounds have been increased
    - The hashing scheme has changed
    
    Use this to transparently upgrade hashes on login:
    
        if needs_rehash(stored_hash):
            new_hash = hash_password(plain_password)
            # update in database
    
    Args:
        hashed_password: The stored hash to check
    
    Returns:
        True if the hash should be regenerated
    """
    return pwd_context.needs_update(hashed_password)
```

---

## Performance at 500-User Scale

| Metric | Value |
|--------|-------|
| Hash time (12 rounds) | ~250ms |
| Verify time | ~250ms |
| 500 concurrent logins | ~125 seconds (serial) / ~2.5 sec (parallel, 100 workers) |
| Memory per hash | Negligible (~4KB) |
| bcrypt output size | 60 bytes |

> At 500 users, even worst-case (all users login simultaneously), bcrypt is not a bottleneck.
> The async FastAPI server handles this well since hashing is CPU-bound but brief.

---

## Security Properties

| Property | Details |
|----------|---------|
| **Algorithm** | bcrypt (Blowfish-based) |
| **Rounds** | 12 (2^12 = 4,096 iterations) |
| **Salt** | Auto-generated per hash (22 chars) |
| **Output** | 60-char string: `$2b$12$<salt><hash>` |
| **Timing safety** | `passlib` uses constant-time comparison |
| **Rehashing** | `needs_rehash()` supports transparent upgrades |

---

## `__init__.py` for Authentication Package

```python
"""
Authentication package init.
Place this file at: backend/app/authentication/__init__.py
"""

# This makes the directory a Python package
```

---

**End of Password Handler Document**
