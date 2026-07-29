# 🛡️ Auth Dependencies — FastAPI Dependency Injection

> `get_current_client`, `require_active_client`, `require_admin`

---

## Overview

FastAPI dependency functions for protecting routes with JWT authentication.
Place this file at: `backend/app/authentication/dependencies.py`

---

## File: `app/authentication/dependencies.py`

```python
"""
Authentication dependencies for FastAPI.
Place this file at: backend/app/authentication/dependencies.py

Usage in routes:
    @router.get("/protected")
    async def protected_route(
        client: Client = Depends(require_active_client),
    ):
        return {"client_id": client.id}
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models.client import Client
from app.authentication.jwt_handler import decode_access_token

logger = logging.getLogger(__name__)


# ============================================================
# OAUTH2 SCHEME
# ============================================================

# This tells FastAPI/Swagger where to get the token
# The tokenUrl points to the login endpoint
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    auto_error=True,  # Automatically returns 401 if no token
)

# Optional version — doesn't error if no token
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    auto_error=False,
)


# ============================================================
# CORE DEPENDENCY: Get Current Client
# ============================================================

async def get_current_client(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Client:
    """
    Extract and validate JWT token, then fetch the client from DB.
    
    This is the base dependency for all authenticated routes.
    
    Flow:
        1. Extract token from Authorization: Bearer header
        2. Decode and validate JWT
        3. Extract client_id from 'sub' claim
        4. Fetch client from database
        5. Return Client model instance
    
    Raises:
        HTTPException 401: Invalid/expired token or client not found
    
    Usage:
        @router.get("/protected")
        async def route(client: Client = Depends(get_current_client)):
            ...
    """
    # 1-2. Decode token (validates signature + expiry)
    payload = decode_access_token(token)
    
    # 3. Extract client_id
    client_id_str = payload.get("sub")
    if not client_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        client_id = int(client_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: malformed subject",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 4. Fetch client from DB
    result = await db.execute(
        select(Client).where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Client not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 5. Return client
    return client


# ============================================================
# DEPENDENCY: Require Active Client
# ============================================================

async def require_active_client(
    client: Client = Depends(get_current_client),
) -> Client:
    """
    Ensure the authenticated client has an 'active' status.
    
    Use this for routes that should reject suspended/locked accounts.
    
    Raises:
        HTTPException 403: Account is not active
    
    Usage:
        @router.get("/dashboard")
        async def route(client: Client = Depends(require_active_client)):
            ...
    """
    if not client.is_active:
        detail = "Account is not active"
        if client.status == "suspended":
            detail = "Account suspended. Contact support."
        elif client.status == "locked":
            detail = "Account locked due to too many failed login attempts."
        elif client.status == "inactive":
            detail = "Account is inactive."
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )
    
    return client


# ============================================================
# DEPENDENCY: Require Admin Role
# ============================================================

async def require_admin(
    client: Client = Depends(require_active_client),
) -> Client:
    """
    Ensure the authenticated client has admin privileges.
    
    Valid roles: 'admin', 'super_admin'
    
    Raises:
        HTTPException 403: Not an admin
    
    Usage:
        @router.get("/admin/clients")
        async def route(client: Client = Depends(require_admin)):
            ...
    """
    if not client.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    
    return client


# ============================================================
# DEPENDENCY: Require Super Admin
# ============================================================

async def require_super_admin(
    client: Client = Depends(require_active_client),
) -> Client:
    """
    Ensure the client has super_admin role.
    
    Raises:
        HTTPException 403: Not a super admin
    
    Usage:
        @router.delete("/admin/clients/{id}")
        async def route(client: Client = Depends(require_super_admin)):
            ...
    """
    if client.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    
    return client


# ============================================================
# DEPENDENCY: Optional Authentication
# ============================================================

async def get_current_client_optional(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: AsyncSession = Depends(get_db),
) -> Optional[Client]:
    """
    Optionally authenticate — returns None if no token provided.
    
    Use for routes that work for both authenticated and anonymous users
    (e.g., public API with enhanced features for logged-in users).
    
    Usage:
        @router.get("/public-endpoint")
        async def route(
            client: Optional[Client] = Depends(get_current_client_optional)
        ):
            if client:
                # authenticated user logic
            else:
                # anonymous user logic
    """
    if not token:
        return None
    
    try:
        return await get_current_client(token=token, db=db)
    except HTTPException:
        return None
```

---

## Dependency Chain

```
oauth2_scheme (extract Bearer token)
       │
       ▼
get_current_client (decode JWT + fetch from DB)
       │
       ├──► require_active_client (check status == 'active')
       │           │
       │           ├──► require_admin (check role in admin/super_admin)
       │           │
       │           └──► require_super_admin (check role == super_admin)
       │
       └──► get_current_client_optional (returns None if no token)
```

---

## Usage Examples

```python
from app.authentication.dependencies import (
    get_current_client,
    require_active_client,
    require_admin,
    get_current_client_optional,
)

# Any authenticated user
@router.get("/profile")
async def get_profile(client: Client = Depends(get_current_client)):
    return {"email": client.email}

# Only active users
@router.get("/dashboard")
async def dashboard(client: Client = Depends(require_active_client)):
    return {"welcome": client.company_name}

# Only admins
@router.get("/admin/users")
async def list_users(admin: Client = Depends(require_admin)):
    return {"admin": admin.email}

# Optional auth (public + enhanced)
@router.get("/public")
async def public(client: Optional[Client] = Depends(get_current_client_optional)):
    if client:
        return {"user": client.email, "personalized": True}
    return {"personalized": False}
```

---

**End of Auth Dependencies Document**
