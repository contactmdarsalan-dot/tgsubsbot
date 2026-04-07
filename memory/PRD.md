# TgSubsBot - Production SaaS Platform

## Original Problem Statement
Transforming a Telegram Subscription Bot into a scalable, market-ready SaaS product with full Multi-Tenant isolation, distinct RBAC, dynamic subscription plans, analytical Super Admin Dashboard, and conversion-focused Landing Page & Mini App.

## Architecture
- **Backend**: FastAPI (Python) with Repository Pattern for strict tenant isolation
- **Frontend**: React with role-based route guards
- **Database**: MongoDB (shared DB, shared schema, strict tenant_id isolation)
- **Auth**: JWT with access/refresh token architecture + token_version for forced logout
- **Scheduler**: APScheduler with MongoDB-based distributed locking (can run embedded or standalone)

## Core Requirements
1. Full Multi-Tenant SaaS isolation across database, backend, and webhooks
2. Distinct RBAC: Super Admins vs. Tenant Admins vs. Bot Admins
3. Super Admin UI: Complete tenant, subscription, and trial management
4. Mini App & Landing Page UI: Highly optimized for conversion

## What's Been Implemented

### Phase 1: Core SaaS Infrastructure (Complete)
- Multi-tenant database isolation with compound unique indexes
- JWT authentication with role + tenant_id
- RBAC: Super Admin, Tenant Admin, Tenant Owner, Bot Admin
- Tenant registration with 14-day auto-trial

### Phase 2: Super Admin Control Center (Complete)
- SaaS Management dashboard (5 tabs: Overview, Tenants, Admins, Subscriptions, Trials)
- Impersonation Mode for Super Admins
- Risk & Alerts Dashboard
- Global analytics

### Phase 3: Frontend & UX (Complete)
- Conversion-focused Landing Page
- Tenant Registration UI
- Role-based sidebar isolation
- Deep space/jewel luxury dark theme

### Phase 4: Security Hardening (Complete)
- Eliminated all SUPER_ADMIN_EMAILS bypass — strict RBAC only
- Eliminated DEFAULT_TENANT_ID fallback — no cross-tenant data leaks
- JWT strictness with role, tenant_id, token_version in payloads
- MongoDB compound unique indexes for safe multi-tenancy
- Repository pattern for all tenant-owned collections
- Token refresh architecture with forced logout capability

### Phase 5: Architecture Refactoring (Complete)
- Refactored `telegram_webhook.py` (4300 lines) into thin dispatcher + modular handlers
- Extracted APScheduler to `workers/scheduler.py` with standalone mode support
- Repository pattern migration: ALL tenant-owned collections use TenantScopedRepository
- Payment idempotency via MongoDB-based dedup locks on Razorpay callbacks
- JWT refresh tokens (2hr access + 30d refresh + token_version)
- Frontend role-based route guards (SuperAdminRoute, TenantRoute, ProtectedRoute)

## Key API Endpoints
- `POST /api/auth/login` — Returns access + refresh token
- `POST /api/auth/register` — Tenant registration with auto-trial
- `POST /api/auth/refresh` — Exchange refresh token for new access token
- `POST /api/auth/logout` — Invalidate all sessions (increments token_version)
- `POST /api/auth/force-logout/{user_id}` — Super Admin force logout
- `POST /api/admin/impersonate` — Super Admin impersonation
- `GET /api/admin/risk-alerts` — Risk & Alerts dashboard
- `GET /api/analytics` — Dashboard analytics
- `GET /api/saas/tenants` — Tenant management

## Database Schema
- `users`: id, email, role, tenant_id, token_version, trial_end_date
- `tenants`: id, name, owner_email, status
- `plans`, `subscribers`, `payments`, `broadcasts`, `templates`: All with tenant_id
- `idempotency_keys`: key (unique), status, expires_at
- `scheduler_locks`: lock_name, acquired_at, expires_at

## 3rd Party Integrations
- Telegram WebApp SDK & Bot API (requires user bot token)
- Razorpay Payments (requires user API key)
- Resend Email OTPs (MOCKED — requires user API key)
- OpenAI GPT-5.2 Vision (uses Emergent LLM Key)

## Remaining P1 Tasks
- None — all P1 tasks complete

## P2/P3 Backlog
- (P2) Move file uploads to Object Storage (S3/R2)
- (P2) Analytics Dashboard (Razorpay vs QR comparison)
- (P2) Complete backend restructuring to target DDD architecture
- (P3) WhatsApp integration
- (P3) Multi-language bot support

## Credentials
- Super Admin: gamerxboys8958@gmail.com / Sumit@8958
- Tenant Admin: anamika@test.com / Admin123
