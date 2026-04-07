# CHANGELOG

## 2026-04-07 — DDD Architecture Restructuring (Iteration 41)
- **Complete Backend Restructuring to DDD Architecture**:
  - Created `core/` layer: `config.py`, `db.py`, `rate_limiter.py`, `exceptions.py`, `constants.py`
  - Created `dependencies/` layer: `auth.py`, `permissions.py` (FastAPI DI)
  - Created `middleware/` layer: `request_id.py`, `idempotency.py`
  - Created `schemas/` layer: `auth.py`, `tenant.py`, `plan.py`, `payment.py`, `broadcast.py`
  - Reorganized `routes/` → `api/` with 5 audience-based sub-packages:
    - `api/public/` (auth routes)
    - `api/tenant_admin/` (10 route modules)
    - `api/platform_admin/` (admin/SaaS management)
    - `api/customer/` (5 mini app route modules)
    - `api/webhooks/` (Telegram, Razorpay)
  - Created backward-compatible re-export wrappers at old `routes/` locations
  - Created `scripts/` with operational tooling: `verify_isolation.py`, `rebuild_indexes.py`, `backfill_tenant_ids.py`
  - Updated `server.py` to import from new `api/` and `core/` layers
  - Fixed `.env` path resolution in `core/config.py` (ROOT_DIR parent.parent)

## 2026-04-07 — P1 Features Completion (Iteration 40)
- Repository Pattern Complete Migration (22 collection repos)
- Payment Idempotency via MongoDB-based dedup locks
- JWT Refresh Token Architecture (access 2hr + refresh 30d + token_version)
- Scheduler Process Separation (embedded + standalone modes)
- Frontend Role-based Route Guards

## Previous Sessions
- Strict Row-Level Tenant Isolation
- SUPER_ADMIN_EMAILS bypass eliminated
- DEFAULT_TENANT_ID fallback eradicated
- Webhook refactoring (4300 lines → modular handlers)
- Impersonation Mode + Risk & Alerts Dashboard
- High-conversion Landing Page + Tenant Registration UI
- Complete CRUD for Tenant Admins and Subscriptions
