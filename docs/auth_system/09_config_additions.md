# ⚙️ Config Additions — JWT & Auth Settings

> New settings to add to the existing config.py

---

## Overview

These settings extend the existing
[config.py](file:///c:/Users/lordk/OneDrive/Desktop/TriAnSer/api-security-system/backend/app/core/config.py)
`Settings` class. **Do not replace the file** — add these fields to the existing class.

---

## New Fields to Add to `Settings` Class

```python
# ============================================================
# ADD THESE FIELDS to the existing Settings class in:
# backend/app/core/config.py
# ============================================================

class Settings(BaseSettings):
    # ... existing fields stay as-is ...
    
    # ─────────────────────────────────────────────────────────
    # NEW: JWT Authentication Settings
    # ─────────────────────────────────────────────────────────
    
    # Secret key for signing JWT tokens
    # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_use_secrets_token_hex_32"
    
    # JWT signing algorithm
    JWT_ALGORITHM: str = "HS256"
    
    # Access token expiry (minutes)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Refresh token expiry (days)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Password reset token expiry (minutes)
    PASSWORD_RESET_EXPIRE_MINUTES: int = 15
    
    # bcrypt hashing rounds
    BCRYPT_ROUNDS: int = 12
    
    # Brute-force protection
    MAX_FAILED_LOGIN_ATTEMPTS: int = 10
    ACCOUNT_LOCKOUT_MINUTES: int = 30
```

---

## Environment Variables (`.env` file)

Add these to your `.env` file:

```env
# ============================================================
# JWT Authentication Settings
# ============================================================

# CRITICAL: Generate a unique secret key for production!
# Run: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=your_64_char_hex_secret_key_here

# Token expiry settings
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
PASSWORD_RESET_EXPIRE_MINUTES=15

# Password hashing
BCRYPT_ROUNDS=12

# Brute-force protection
MAX_FAILED_LOGIN_ATTEMPTS=10
ACCOUNT_LOCKOUT_MINUTES=30
```

---

## Generate a Secure JWT Secret Key

Run this command to generate a production-safe secret key:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Example output:
```
a3f8b2c1d4e5f6789012345678901234abcdef1234567890abcdef1234567890
```

> ⚠️ **Never commit the production secret key to version control!**

---

## Updated `config.py` (Complete File)

Here's what the complete config file looks like after adding auth settings:

```python
"""
Application configuration.
File: backend/app/core/config.py
"""

from pydantic_settings import BaseSettings
import os
from enum import Enum
from typing import List


class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class Settings(BaseSettings):
    # ─────────────────────────────────────────────────────────
    # Application
    # ─────────────────────────────────────────────────────────
    APP_NAME: str = "AI-Powered API Security System"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    DEBUG: bool = True

    # ─────────────────────────────────────────────────────────
    # Server
    # ─────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # ─────────────────────────────────────────────────────────
    # Database
    # ─────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:5501@localhost:5513/api_security"

    # ─────────────────────────────────────────────────────────
    # Redis
    # ─────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"

    # ─────────────────────────────────────────────────────────
    # Security (existing)
    # ─────────────────────────────────────────────────────────
    RATE_LIMIT_WINDOW: int = 60
    MAX_REQUESTS_PER_MINUTE: int = 100

    # Block durations
    BLOCK_SOFT_DURATION: int = 120
    BLOCK_MEDIUM_DURATION: int = 600
    BLOCK_HARD_DURATION: int = 3600

    # ─────────────────────────────────────────────────────────
    # JWT Authentication (NEW)
    # ─────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_use_secrets_token_hex_32"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_EXPIRE_MINUTES: int = 15
    BCRYPT_ROUNDS: int = 12
    MAX_FAILED_LOGIN_ATTEMPTS: int = 10
    ACCOUNT_LOCKOUT_MINUTES: int = 30

    # ─────────────────────────────────────────────────────────
    # Logging
    # ─────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ─────────────────────────────────────────────────────────
    # Feature thresholds (existing)
    # ─────────────────────────────────────────────────────────
    HIGH_REQUEST_THRESHOLD: int = 50
    HIGH_RATIO_THRESHOLD: float = 0.8
    HIGH_ENTROPY_THRESHOLD: float = 0.7

    class Config:
        env_file = os.path.join(os.path.dirname(__file__), "../../../.env")
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
```

---

## Required New Dependencies

Add to `requirements.txt`:

```
# JWT Authentication
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
bcrypt>=4.0.0
email-validator>=2.0.0
```

---

**End of Config Additions Document**
