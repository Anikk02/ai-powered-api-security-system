# 🗄️ Database Schema — JWT Authentication System

> PostgreSQL schema for 400–500 user authentication

---

## Overview

Three new tables extend the existing `api_security` database:

| Table | Purpose | Rows (est.) |
|-------|---------|-------------|
| `clients` | User accounts for authentication | 400–500 |
| `refresh_tokens` | JWT refresh token storage | ~1,000–2,500 |
| `password_reset_tokens` | Temporary password reset tokens | ~50–100 active |

---

## 1. Clients Table

```sql
-- ============================================================
-- CLIENTS TABLE
-- Core user accounts for JWT authentication
-- Designed for 400-500 users with room to scale to 5,000+
-- ============================================================

CREATE TABLE clients (
    id              BIGSERIAL       PRIMARY KEY,
    email           VARCHAR(255)    UNIQUE NOT NULL,
    password_hash   VARCHAR(255)    NOT NULL,
    company_name    VARCHAR(255),
    
    -- Role-based access
    role            VARCHAR(50)     NOT NULL DEFAULT 'client',
    -- Possible values: 'client', 'admin', 'super_admin'
    
    -- Account status
    status          VARCHAR(50)     NOT NULL DEFAULT 'active',
    -- Possible values: 'active', 'inactive', 'suspended', 'locked'
    
    -- Email verification (optional for MVP)
    email_verified  BOOLEAN         NOT NULL DEFAULT FALSE,
    
    -- Brute-force protection
    failed_login_attempts   INTEGER     NOT NULL DEFAULT 0,
    locked_until            TIMESTAMP   WITH TIME ZONE,
    
    -- Timestamps
    created_at      TIMESTAMP WITH TIME ZONE    NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE    NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMP WITH TIME ZONE
);

-- ============================================================
-- INDEXES for clients
-- ============================================================

-- Primary lookup: login by email (unique already creates index)
-- No additional index needed for email

-- Filter by status (for admin queries)
CREATE INDEX idx_clients_status ON clients (status);

-- Filter by role (for admin queries)
CREATE INDEX idx_clients_role ON clients (role);

-- Composite: active clients sorted by creation date (dashboard listing)
CREATE INDEX idx_clients_active_created 
    ON clients (created_at DESC) 
    WHERE status = 'active';
```

---

## 2. Refresh Tokens Table

```sql
-- ============================================================
-- REFRESH TOKENS TABLE
-- Stores hashed refresh tokens for JWT rotation
-- Each client can have multiple active sessions (multi-device)
-- ============================================================

CREATE TABLE refresh_tokens (
    id              BIGSERIAL       PRIMARY KEY,
    client_id       BIGINT          NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    
    -- Store hash of token, never the raw token
    token_hash      VARCHAR(255)    NOT NULL UNIQUE,
    
    -- Expiration
    expires_at      TIMESTAMP WITH TIME ZONE    NOT NULL,
    
    -- Revocation
    revoked         BOOLEAN         NOT NULL DEFAULT FALSE,
    revoked_at      TIMESTAMP WITH TIME ZONE,
    
    -- Device/session tracking (optional)
    device_info     VARCHAR(500),
    ip_address      VARCHAR(45),    -- supports IPv6
    
    -- Timestamps
    created_at      TIMESTAMP WITH TIME ZONE    NOT NULL DEFAULT NOW()
);

-- ============================================================
-- INDEXES for refresh_tokens
-- ============================================================

-- Lookup by token hash (login/refresh flow)
-- UNIQUE constraint already creates index on token_hash

-- Find all tokens for a client (logout-all, session management)
CREATE INDEX idx_refresh_tokens_client_id 
    ON refresh_tokens (client_id);

-- Cleanup expired/revoked tokens (background job)
CREATE INDEX idx_refresh_tokens_expires 
    ON refresh_tokens (expires_at) 
    WHERE revoked = FALSE;

-- Find active tokens for a client
CREATE INDEX idx_refresh_tokens_client_active 
    ON refresh_tokens (client_id, created_at DESC) 
    WHERE revoked = FALSE;
```

---

## 3. Password Reset Tokens Table

```sql
-- ============================================================
-- PASSWORD RESET TOKENS TABLE
-- Short-lived tokens for password reset flow
-- ============================================================

CREATE TABLE password_reset_tokens (
    id              BIGSERIAL       PRIMARY KEY,
    client_id       BIGINT          NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    
    -- Store hash of token, never the raw token
    token_hash      VARCHAR(255)    NOT NULL UNIQUE,
    
    -- Short-lived: 15 minutes
    expires_at      TIMESTAMP WITH TIME ZONE    NOT NULL,
    
    -- Single use
    used            BOOLEAN         NOT NULL DEFAULT FALSE,
    used_at         TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at      TIMESTAMP WITH TIME ZONE    NOT NULL DEFAULT NOW()
);

-- ============================================================
-- INDEXES for password_reset_tokens
-- ============================================================

-- Lookup by token hash (reset flow)
-- UNIQUE constraint already creates index on token_hash

-- Find pending resets for a client (prevent spam)
CREATE INDEX idx_password_reset_client 
    ON password_reset_tokens (client_id, created_at DESC) 
    WHERE used = FALSE;

-- Cleanup expired tokens
CREATE INDEX idx_password_reset_expires 
    ON password_reset_tokens (expires_at) 
    WHERE used = FALSE;
```

---

## 4. Trigger: Auto-Update `updated_at`

```sql
-- ============================================================
-- TRIGGER: Auto-update updated_at on clients
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_clients_updated_at
    BEFORE UPDATE ON clients
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

---

## 5. Cleanup: Expired Tokens

```sql
-- ============================================================
-- SCHEDULED CLEANUP (run via pg_cron or background task)
-- Remove expired/used tokens older than 30 days
-- ============================================================

-- Cleanup expired refresh tokens
DELETE FROM refresh_tokens 
WHERE (expires_at < NOW() AND revoked = FALSE)
   OR (revoked = TRUE AND revoked_at < NOW() - INTERVAL '30 days');

-- Cleanup used/expired password reset tokens
DELETE FROM password_reset_tokens 
WHERE (expires_at < NOW())
   OR (used = TRUE AND used_at < NOW() - INTERVAL '7 days');
```

---

## 6. Performance Notes for 500 Users

| Metric | Value | Rationale |
|--------|-------|-----------|
| `clients` rows | ~500 | One per user |
| `refresh_tokens` rows | ~1,000–2,500 | ~2–5 active sessions per user |
| `password_reset_tokens` rows | ~50 active | Most expire/get used quickly |
| Email lookup | O(log n) via UNIQUE index | < 1ms for 500 rows |
| Token lookup | O(log n) via UNIQUE index | < 1ms |
| Connection pool | 50 + 100 overflow | Matches existing session.py |

> At 500 users, all lookups will be in-memory (index fits in RAM). No partitioning or sharding needed.

---

## 7. Relationship Diagram

```
┌─────────────────────┐
│      clients        │
├─────────────────────┤
│ id (PK)             │──┐
│ email (UNIQUE)      │  │
│ password_hash       │  │
│ company_name        │  │
│ role                │  │
│ status              │  │
│ email_verified      │  │
│ failed_login_attempts│  │
│ locked_until        │  │
│ created_at          │  │
│ updated_at          │  │
│ last_login_at       │  │
└─────────────────────┘  │
         │               │
         │  1:N           │  1:N
         ▼               ▼
┌──────────────────┐  ┌──────────────────────┐
│  refresh_tokens  │  │ password_reset_tokens │
├──────────────────┤  ├──────────────────────┤
│ id (PK)          │  │ id (PK)              │
│ client_id (FK)   │  │ client_id (FK)       │
│ token_hash (UQ)  │  │ token_hash (UQ)      │
│ expires_at       │  │ expires_at           │
│ revoked          │  │ used                 │
│ revoked_at       │  │ used_at              │
│ device_info      │  │ created_at           │
│ ip_address       │  └──────────────────────┘
│ created_at       │
└──────────────────┘
```

---

**End of Schema Document**
