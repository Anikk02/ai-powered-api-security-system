# 🧪 Testing Guide — Auth System Verification

> curl commands, pytest tests, and 500-user load testing

---

## Overview

This guide covers three levels of testing:
1. **Manual testing** with `curl` commands
2. **Automated testing** with `pytest` (async)
3. **Load testing** with `httpx` for 500 concurrent users

---

## 1. Manual Testing with curl

### Prerequisites

```bash
# Ensure the backend is running
cd backend
uvicorn app.main:app --reload --port 8000

# Ensure PostgreSQL is running on port 5513
# Ensure tables are created and seeded (see 10_migration_seed_script.md)
```

---

### 1.1 Register a New Client

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com",
    "password": "SecurePass123",
    "company_name": "My Company"
  }'
```

**Expected Response (201):**
```json
{
    "id": 503,
    "email": "newuser@example.com",
    "company_name": "My Company",
    "role": "client",
    "status": "active",
    "message": "Registration successful"
}
```

**Error — Duplicate Email (409):**
```json
{
    "detail": "Email already registered"
}
```

**Error — Weak Password (422):**
```json
{
    "detail": [
        {
            "msg": "Password must contain at least one uppercase letter",
            "type": "value_error"
        }
    ]
}
```

---

### 1.2 Login

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@triansec.dev",
    "password": "AdminPass123"
  }'
```

**Expected Response (200):**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "dGhpcyBpcyBhIHJhbmRvbSByZWZyZXNoIHRva2Vu...",
    "token_type": "bearer",
    "expires_in": 1800
}
```

**Save the tokens:**
```bash
# Save for subsequent requests
ACCESS_TOKEN="eyJhbGci..."
REFRESH_TOKEN="dGhpcyBp..."
```

---

### 1.3 Get Current User Profile

```bash
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

**Expected Response (200):**
```json
{
    "id": 501,
    "email": "admin@triansec.dev",
    "company_name": "TrianSec Admin",
    "role": "super_admin",
    "status": "active",
    "email_verified": true,
    "created_at": "2026-06-19T10:30:00Z",
    "updated_at": "2026-06-19T10:30:00Z",
    "last_login_at": "2026-06-19T10:45:00Z"
}
```

---

### 1.4 Refresh Access Token

```bash
curl -X POST http://localhost:8000/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{
    \"refresh_token\": \"$REFRESH_TOKEN\"
  }"
```

**Expected Response (200):**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiJ9...(new token)...",
    "token_type": "bearer",
    "expires_in": 1800
}
```

---

### 1.5 Forgot Password

```bash
curl -X POST http://localhost:8000/api/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{
    "email": "client@triansec.dev"
  }'
```

**Expected Response (200 — development mode):**
```json
{
    "message": "If the email exists, a reset link has been sent",
    "reset_token": "abc123def456..."
}
```

---

### 1.6 Reset Password

```bash
RESET_TOKEN="abc123def456..."

curl -X POST http://localhost:8000/api/auth/reset-password \
  -H "Content-Type: application/json" \
  -d "{
    \"token\": \"$RESET_TOKEN\",
    \"new_password\": \"NewSecure456\"
  }"
```

**Expected Response (200):**
```json
{
    "message": "Password reset successful. Please login with your new password."
}
```

---

### 1.7 Change Password (Authenticated)

```bash
curl -X POST http://localhost:8000/api/auth/change-password \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "AdminPass123",
    "new_password": "NewAdmin789"
  }'
```

---

### 1.8 Logout

```bash
curl -X POST http://localhost:8000/api/auth/logout \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"refresh_token\": \"$REFRESH_TOKEN\"
  }"
```

---

### 1.9 Logout All Devices

```bash
curl -X POST http://localhost:8000/api/auth/logout-all \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

---

## 2. Automated Testing with pytest

### Setup

```bash
pip install pytest pytest-asyncio httpx
```

### File: `tests/test_auth.py`

```python
"""
Pytest tests for authentication endpoints.
Place this file at: backend/tests/test_auth.py

Run: pytest tests/test_auth.py -v
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app


BASE_URL = "http://test"


@pytest_asyncio.fixture
async def client():
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:
        yield ac


@pytest.fixture
def new_user_data():
    """Fresh user data for registration tests."""
    import uuid
    unique = uuid.uuid4().hex[:8]
    return {
        "email": f"test_{unique}@example.com",
        "password": "TestPass123",
        "company_name": f"Test Company {unique}",
    }


# ============================================================
# REGISTRATION TESTS
# ============================================================

@pytest.mark.asyncio
async def test_register_success(client, new_user_data):
    """Test successful registration."""
    response = await client.post("/api/auth/register", json=new_user_data)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == new_user_data["email"]
    assert data["role"] == "client"
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_register_duplicate_email(client, new_user_data):
    """Test duplicate email rejection."""
    # Register once
    await client.post("/api/auth/register", json=new_user_data)
    # Try again
    response = await client.post("/api/auth/register", json=new_user_data)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_register_weak_password(client):
    """Test password validation."""
    response = await client.post("/api/auth/register", json={
        "email": "weak@example.com",
        "password": "weak",  # Too short, no uppercase/digit
    })
    assert response.status_code == 422


# ============================================================
# LOGIN TESTS
# ============================================================

@pytest.mark.asyncio
async def test_login_success(client, new_user_data):
    """Test successful login."""
    # Register first
    await client.post("/api/auth/register", json=new_user_data)
    
    # Login
    response = await client.post("/api/auth/login", json={
        "email": new_user_data["email"],
        "password": new_user_data["password"],
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800


@pytest.mark.asyncio
async def test_login_wrong_password(client, new_user_data):
    """Test login with wrong password."""
    await client.post("/api/auth/register", json=new_user_data)
    
    response = await client.post("/api/auth/login", json={
        "email": new_user_data["email"],
        "password": "WrongPass123",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_email(client):
    """Test login with non-existent email."""
    response = await client.post("/api/auth/login", json={
        "email": "nonexistent@example.com",
        "password": "SomePass123",
    })
    assert response.status_code == 401


# ============================================================
# TOKEN TESTS
# ============================================================

@pytest.mark.asyncio
async def test_access_protected_route(client, new_user_data):
    """Test accessing /me with valid token."""
    await client.post("/api/auth/register", json=new_user_data)
    login_resp = await client.post("/api/auth/login", json={
        "email": new_user_data["email"],
        "password": new_user_data["password"],
    })
    token = login_resp.json()["access_token"]
    
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == new_user_data["email"]


@pytest.mark.asyncio
async def test_access_without_token(client):
    """Test accessing protected route without token."""
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_access_with_invalid_token(client):
    """Test accessing protected route with invalid token."""
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client, new_user_data):
    """Test refreshing access token."""
    await client.post("/api/auth/register", json=new_user_data)
    login_resp = await client.post("/api/auth/login", json={
        "email": new_user_data["email"],
        "password": new_user_data["password"],
    })
    refresh_token = login_resp.json()["refresh_token"]
    
    response = await client.post("/api/auth/refresh", json={
        "refresh_token": refresh_token,
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


# ============================================================
# PASSWORD RESET TESTS
# ============================================================

@pytest.mark.asyncio
async def test_forgot_password(client, new_user_data):
    """Test forgot password flow."""
    await client.post("/api/auth/register", json=new_user_data)
    
    response = await client.post("/api/auth/forgot-password", json={
        "email": new_user_data["email"],
    })
    assert response.status_code == 200
    # In dev mode, reset_token is included
    data = response.json()
    assert "message" in data


@pytest.mark.asyncio
async def test_forgot_password_nonexistent(client):
    """Test forgot password with non-existent email (should still return 200)."""
    response = await client.post("/api/auth/forgot-password", json={
        "email": "nonexistent@example.com",
    })
    assert response.status_code == 200  # Never reveal if email exists


# ============================================================
# LOGOUT TESTS
# ============================================================

@pytest.mark.asyncio
async def test_logout(client, new_user_data):
    """Test logout revokes refresh token."""
    await client.post("/api/auth/register", json=new_user_data)
    login_resp = await client.post("/api/auth/login", json={
        "email": new_user_data["email"],
        "password": new_user_data["password"],
    })
    tokens = login_resp.json()
    
    # Logout
    response = await client.post(
        "/api/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200
    
    # Try to use revoked refresh token
    response = await client.post("/api/auth/refresh", json={
        "refresh_token": tokens["refresh_token"],
    })
    assert response.status_code == 401
```

### Run Tests

```bash
cd backend
pytest tests/test_auth.py -v --tb=short
```

---

## 3. Load Testing — 500 Concurrent Users

### File: `scripts/load_test_auth.py`

```python
"""
Load test: Simulate 500 concurrent users performing auth operations.
Place this file at: backend/scripts/load_test_auth.py

Usage:
    pip install httpx
    python scripts/load_test_auth.py
"""

import asyncio
import time
import statistics
from typing import List, Dict
import httpx

# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "http://localhost:8000"
TOTAL_USERS = 500
CONCURRENT_BATCH = 50  # Process 50 at a time
DEFAULT_PASSWORD = "TestPass123"


# ============================================================
# LOAD TEST FUNCTIONS
# ============================================================

async def login_user(
    client: httpx.AsyncClient,
    email: str,
    password: str,
) -> Dict:
    """Login a single user and return timing info."""
    start = time.perf_counter()
    try:
        response = await client.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": email, "password": password},
            timeout=30.0,
        )
        elapsed = (time.perf_counter() - start) * 1000  # ms
        
        return {
            "email": email,
            "status": response.status_code,
            "elapsed_ms": elapsed,
            "success": response.status_code == 200,
            "tokens": response.json() if response.status_code == 200 else None,
        }
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return {
            "email": email,
            "status": 0,
            "elapsed_ms": elapsed,
            "success": False,
            "error": str(e),
        }


async def access_me(
    client: httpx.AsyncClient,
    access_token: str,
) -> Dict:
    """Access /me endpoint with token."""
    start = time.perf_counter()
    try:
        response = await client.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        elapsed = (time.perf_counter() - start) * 1000
        return {
            "status": response.status_code,
            "elapsed_ms": elapsed,
            "success": response.status_code == 200,
        }
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return {"status": 0, "elapsed_ms": elapsed, "success": False}


async def run_load_test():
    """Run the complete load test."""
    
    print("=" * 60)
    print(f"  LOAD TEST: {TOTAL_USERS} Users")
    print("=" * 60)
    print()
    
    # ─────────────────────────────────────────────────────────
    # Phase 1: Login all 500 users
    # ─────────────────────────────────────────────────────────
    print("📌 Phase 1: Login 500 users")
    print(f"   Batch size: {CONCURRENT_BATCH}")
    print()
    
    login_results: List[Dict] = []
    
    async with httpx.AsyncClient() as client:
        overall_start = time.perf_counter()
        
        for batch_start in range(0, TOTAL_USERS, CONCURRENT_BATCH):
            batch_end = min(batch_start + CONCURRENT_BATCH, TOTAL_USERS)
            
            tasks = []
            for i in range(batch_start + 1, batch_end + 1):
                email = f"testuser{i:04d}@triansec.dev"
                tasks.append(login_user(client, email, DEFAULT_PASSWORD))
            
            results = await asyncio.gather(*tasks)
            login_results.extend(results)
            
            success_count = sum(1 for r in results if r["success"])
            print(f"   Batch {batch_start+1}-{batch_end}: "
                  f"{success_count}/{len(results)} success")
        
        login_elapsed = (time.perf_counter() - overall_start) * 1000
    
    # Analyze login results
    successful_logins = [r for r in login_results if r["success"]]
    failed_logins = [r for r in login_results if not r["success"]]
    login_times = [r["elapsed_ms"] for r in successful_logins]
    
    print()
    print(f"   ✅ Successful: {len(successful_logins)}")
    print(f"   ❌ Failed: {len(failed_logins)}")
    if login_times:
        print(f"   ⏱️  Avg: {statistics.mean(login_times):.1f}ms")
        print(f"   ⏱️  P50: {statistics.median(login_times):.1f}ms")
        print(f"   ⏱️  P95: {sorted(login_times)[int(len(login_times)*0.95)]:.1f}ms")
        print(f"   ⏱️  P99: {sorted(login_times)[int(len(login_times)*0.99)]:.1f}ms")
        print(f"   ⏱️  Max: {max(login_times):.1f}ms")
    print(f"   ⏱️  Total: {login_elapsed:.0f}ms")
    
    # ─────────────────────────────────────────────────────────
    # Phase 2: Access /me with all tokens
    # ─────────────────────────────────────────────────────────
    print()
    print("📌 Phase 2: Access /me for all logged-in users")
    
    me_results: List[Dict] = []
    
    async with httpx.AsyncClient() as client:
        me_start = time.perf_counter()
        
        for batch_start in range(0, len(successful_logins), CONCURRENT_BATCH):
            batch = successful_logins[batch_start:batch_start + CONCURRENT_BATCH]
            
            tasks = [
                access_me(client, r["tokens"]["access_token"])
                for r in batch
            ]
            results = await asyncio.gather(*tasks)
            me_results.extend(results)
        
        me_elapsed = (time.perf_counter() - me_start) * 1000
    
    successful_me = [r for r in me_results if r["success"]]
    me_times = [r["elapsed_ms"] for r in successful_me]
    
    print(f"   ✅ Successful: {len(successful_me)}")
    if me_times:
        print(f"   ⏱️  Avg: {statistics.mean(me_times):.1f}ms")
        print(f"   ⏱️  P50: {statistics.median(me_times):.1f}ms")
        print(f"   ⏱️  P95: {sorted(me_times)[int(len(me_times)*0.95)]:.1f}ms")
    print(f"   ⏱️  Total: {me_elapsed:.0f}ms")
    
    # ─────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  LOAD TEST SUMMARY")
    print("=" * 60)
    print(f"  Total users:     {TOTAL_USERS}")
    print(f"  Login success:   {len(successful_logins)} ({len(successful_logins)/TOTAL_USERS*100:.1f}%)")
    print(f"  /me success:     {len(successful_me)} ({len(successful_me)/max(len(successful_logins),1)*100:.1f}%)")
    if login_times:
        print(f"  Login avg:       {statistics.mean(login_times):.1f}ms")
    if me_times:
        print(f"  /me avg:         {statistics.mean(me_times):.1f}ms")
    print()
    
    # Pass/Fail criteria
    all_pass = True
    if len(successful_logins) < TOTAL_USERS * 0.95:
        print("  ❌ FAIL: Login success rate < 95%")
        all_pass = False
    if login_times and statistics.mean(login_times) > 5000:
        print("  ❌ FAIL: Average login time > 5s")
        all_pass = False
    if me_times and statistics.mean(me_times) > 500:
        print("  ❌ FAIL: Average /me time > 500ms")
        all_pass = False
    
    if all_pass:
        print("  ✅ ALL CHECKS PASSED")
    
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_load_test())
```

### Run Load Test

```bash
cd backend
python scripts/load_test_auth.py
```

### Expected Output

```
============================================================
  LOAD TEST: 500 Users
============================================================

📌 Phase 1: Login 500 users
   Batch size: 50
   Batch 1-50: 50/50 success
   Batch 51-100: 50/50 success
   ...
   Batch 451-500: 50/50 success

   ✅ Successful: 500
   ❌ Failed: 0
   ⏱️  Avg: 280.5ms
   ⏱️  P50: 265.2ms
   ⏱️  P95: 450.1ms
   ⏱️  P99: 620.3ms
   ⏱️  Total: 2800ms

📌 Phase 2: Access /me for all logged-in users
   ✅ Successful: 500
   ⏱️  Avg: 12.3ms
   ⏱️  P50: 10.1ms
   ⏱️  P95: 25.4ms
   ⏱️  Total: 615ms

============================================================
  LOAD TEST SUMMARY
============================================================
  Total users:     500
  Login success:   500 (100.0%)
  /me success:     500 (100.0%)
  Login avg:       280.5ms
  /me avg:         12.3ms

  ✅ ALL CHECKS PASSED
============================================================
```

---

## 4. Pass/Fail Criteria

| Test | Threshold | Rationale |
|------|-----------|-----------|
| Login success rate | ≥ 95% | Allows for rare timeouts |
| Login avg time | < 5 seconds | bcrypt is ~250ms + DB overhead |
| /me avg time | < 500ms | JWT decode + DB lookup |
| Refresh avg time | < 200ms | Hash lookup + JWT issue |

---

**End of Testing Guide Document**
