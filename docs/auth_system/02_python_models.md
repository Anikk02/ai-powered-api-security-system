# 🐍 SQLAlchemy Models — JWT Authentication

> Async SQLAlchemy models matching existing project patterns

---

## Overview

These models extend the existing database layer. They follow the same pattern as
[user.py](file:///c:/Users/lordk/OneDrive/Desktop/TriAnSer/api-security-system/backend/app/db/models/user.py)
and use `Base` from
[base.py](file:///c:/Users/lordk/OneDrive/Desktop/TriAnSer/api-security-system/backend/app/db/base.py).

---

## File: `app/db/models/client.py`

```python
"""
Client model for JWT authentication.
Place this file at: backend/app/db/models/client.py
"""

from sqlalchemy import (
    Column, BigInteger, String, Boolean, Integer,
    DateTime, Index
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.db.base import Base


class Client(Base):
    __tablename__ = "clients"

    # Primary key
    id = Column(BigInteger, primary_key=True, index=True)

    # Authentication fields
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    # Profile
    company_name = Column(String(255), nullable=True)

    # Role-based access control
    # Values: 'client', 'admin', 'super_admin'
    role = Column(String(50), nullable=False, default="client")

    # Account status
    # Values: 'active', 'inactive', 'suspended', 'locked'
    status = Column(String(50), nullable=False, default="active")

    # Email verification (optional for MVP)
    email_verified = Column(Boolean, nullable=False, default=False)

    # Brute-force protection
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="client",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    password_reset_tokens = relationship(
        "PasswordResetToken",
        back_populates="client",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    # Table-level indexes
    __table_args__ = (
        Index("idx_clients_status", "status"),
        Index("idx_clients_role", "role"),
    )

    def __repr__(self):
        return f"<Client(id={self.id}, email='{self.email}', role='{self.role}')>"

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def is_locked(self) -> bool:
        if self.locked_until is None:
            return False
        return datetime.now(timezone.utc) < self.locked_until

    @property
    def is_admin(self) -> bool:
        return self.role in ("admin", "super_admin")
```

---

## File: `app/db/models/refresh_token.py`

```python
"""
Refresh token model for JWT token rotation.
Place this file at: backend/app/db/models/refresh_token.py
"""

from sqlalchemy import (
    Column, BigInteger, String, Boolean,
    DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.db.base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    # Primary key
    id = Column(BigInteger, primary_key=True, index=True)

    # Foreign key to clients
    client_id = Column(
        BigInteger,
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False
    )

    # Hashed token (never store raw token)
    token_hash = Column(String(255), unique=True, nullable=False)

    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Revocation
    revoked = Column(Boolean, nullable=False, default=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    # Session/device tracking
    device_info = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)  # Supports IPv6

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    client = relationship("Client", back_populates="refresh_tokens")

    # Table-level indexes
    __table_args__ = (
        Index("idx_refresh_tokens_client_id", "client_id"),
        Index("idx_refresh_tokens_expires", "expires_at"),
    )

    def __repr__(self):
        return (
            f"<RefreshToken(id={self.id}, client_id={self.client_id}, "
            f"revoked={self.revoked})>"
        )

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.revoked and not self.is_expired
```

---

## File: `app/db/models/password_reset_token.py`

```python
"""
Password reset token model.
Place this file at: backend/app/db/models/password_reset_token.py
"""

from sqlalchemy import (
    Column, BigInteger, String, Boolean,
    DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.db.base import Base


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    # Primary key
    id = Column(BigInteger, primary_key=True, index=True)

    # Foreign key to clients
    client_id = Column(
        BigInteger,
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False
    )

    # Hashed token (never store raw token)
    token_hash = Column(String(255), unique=True, nullable=False)

    # Short-lived: 15 minutes
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Single use
    used = Column(Boolean, nullable=False, default=False)
    used_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    client = relationship("Client", back_populates="password_reset_tokens")

    # Table-level indexes
    __table_args__ = (
        Index("idx_password_reset_client", "client_id", "created_at"),
        Index("idx_password_reset_expires", "expires_at"),
    )

    def __repr__(self):
        return (
            f"<PasswordResetToken(id={self.id}, client_id={self.client_id}, "
            f"used={self.used})>"
        )

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.used and not self.is_expired
```

---

## Update: `app/db/models/__init__.py`

Add these imports to the existing
[__init__.py](file:///c:/Users/lordk/OneDrive/Desktop/TriAnSer/api-security-system/backend/app/db/models/__init__.py):

```python
# Existing imports (keep as-is)
from .user import User
from .api_key import APIKey
from .decision_log import DecisionLog
from .request_log import RequestLog
from .feedback import Feedback

# NEW: Authentication models
from .client import Client
from .refresh_token import RefreshToken
from .password_reset_token import PasswordResetToken
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| `BigInteger` for IDs | Matches existing `user.py` pattern |
| `timezone=True` on DateTime | Stores UTC timestamps (best practice) |
| `cascade="all, delete-orphan"` | Auto-cleanup tokens when client deleted |
| `lazy="selectin"` on relationships | Async-compatible eager loading |
| `onupdate` for `updated_at` | Auto-updates on any column change |
| Properties for `is_active`, `is_locked` | Clean API for business logic checks |

---

**End of Models Document**
