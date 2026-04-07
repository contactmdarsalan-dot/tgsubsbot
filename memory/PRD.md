# TgSubsBot - Product Requirements Document

## Original Problem Statement
Transforming a Telegram Subscription Bot into a scalable, market-ready SaaS product. Core requirements include full Multi-Tenant SaaS isolation, distinct RBAC (Super Admin vs. Tenant Admin), dynamic subscription plans, a highly analytical "Control Center" Super Admin Dashboard, and a conversion-focused Landing Page & Mini App.

## Core Requirements
1. Full Multi-Tenant SaaS isolation across database, backend, and webhooks
2. Distinct RBAC: Super Admins vs. Tenant Admins vs. Bot Admins
3. Razorpay integration for Telegram Bot checkout flows
4. "Global Marketplace App" API integration (Wallet, Coins, Revenue Share)
5. Comprehensive Tenant Management via Super Admin Dashboard
6. Impersonation Mode for Super Admins
7. Risk & Alerts system for fraud detection

## User Personas
- **Super Admin**: Platform owner, manages all tenants, views global analytics, can impersonate tenants
- **Tenant Admin/Owner**: Creator who owns a bot, manages subscribers, plans, payments
- **Bot User**: Telegram user who buys plans, accesses content
- **Mini App User**: Accesses creator content via Telegram Mini App

## Tech Stack
- **Backend**: FastAPI (Python)
- **Frontend**: React (CRA with CRACO)
- **Database**: MongoDB (shared DB, shared schema, row-level tenant isolation)
- **Theme**: Neon Green (#c8ff00) on Deep Black

## 3rd Party Integrations
- OpenAI GPT-5.2 Vision (Emergent LLM Key) — Payment screenshot verification
- Razorpay — Bot payment links
- Telegram Bot API — Webhook-based bot management
- Resend — Email OTPs (BLOCKED: domain verification pending)

## Architecture
```
/app/
├── backend/
│   ├── server.py (FastAPI app, RequestContext middleware, super admin bootstrap)
│   ├── config.py (JWT_SECRET with production guard, ENVIRONMENT check)
│   ├── database.py (MongoDB connection, compound indexes)
│   ├── repositories/
│   │   └── base.py (TenantScopedRepository — mandatory tenant isolation)
│   ├── services/
│   │   ├── auth.py (JWT with role/tenant_id)
│   │   ├── permissions.py (Role-only RBAC, no email bypass)
│   │   ├── tenant.py (Tenant resolution with warnings)
│   │   └── audit.py (Enhanced audit logging)
│   ├── routes/
│   │   ├── admin.py (Impersonation, Risk Alerts, Tenant CRUD, Subscriptions)
│   │   ├── auth.py, plans.py, payments.py, subscribers.py
│   │   ├── telegram_webhook.py (~4300 lines, tenant-isolated)
│   │   └── razorpay_webhook.py, global_app.py, global_wallet.py
├── frontend/
│   ├── src/
│   │   ├── App.js (SuperAdminRoute, TenantRoute, ProtectedRoute guards)
│   │   ├── components/Layout.jsx (Role-based sidebar, impersonation banner)
│   │   ├── pages/
│   │   │   ├── RiskAlerts.jsx (NEW — fraud detection UI)
│   │   │   ├── SaaSManagement.jsx (Tenant CRUD + Impersonate button)
│   │   │   └── ... (20+ pages)
```

## Security Model (Production-Hardened)
- **JWT**: Includes `user_id`, `role`, `tenant_id`. Secret MUST be set in production.
- **RBAC**: Role-based only. No email-based bypass anywhere (frontend or backend).
- **Route Guards**: SuperAdminRoute, TenantRoute, ProtectedRoute in frontend.
- **Tenant Isolation**: `tq()` helper + Repository pattern.
- **Impersonation**: Full audit trail, original token preserved for exit.
- **Request Tracing**: X-Request-ID header on every response.
- **Compound Indexes**: `(tenant_id, id)` on all business collections.

## Implemented Features

### Phase 22: Production Security Hardening (2026-04-07)
- JWT enhanced with role/tenant_id
- Email-based super admin bypass removed globally
- JWT_SECRET production guard
- Super Admin Bootstrap at startup
- RequestContext Middleware (X-Request-ID)
- Compound indexes on 12 collections
- Repository pattern base class
- Fixed is_super_admin shadowing bug
- Enhanced audit service

### Phase 23: Impersonation + Risk & Alerts + Route Guards (2026-04-07)
- **Impersonation Mode**: Super Admin can impersonate any tenant admin
  - API: POST /api/saas/impersonate/{tenant_id}
  - Audit log tracking
  - UI: Purple eye icon in tenant table
  - Exit banner with "Exit Impersonation" button
- **Risk & Alerts System**: 5 alert types
  - high_refund_rate (>20% refund rate)
  - failed_payments_spike (>10 failures in 7 days)
  - abandoned_bot (active subs but no payments in 30 days)
  - unusual_volume (>50 payments in 24h)
  - expiry_wave (>20 subs expiring in 3 days)
  - API: GET /api/saas/risk-alerts
  - Dismiss: POST /api/saas/risk-alerts/{alert_id}/dismiss
- **Frontend Route Guards**:
  - SuperAdminRoute: saas-management, risk-alerts, admin-subs, user-management, branding, tenant-profile
  - TenantRoute: plans, subscribers, payments, chat-groups, broadcast, etc.
  - Layout.jsx: Role-only sidebar (no email bypass)

## Prioritized Backlog

### P1 (Next)
- [ ] Remove "default" tenant fallback entirely (needs data backfill script)
- [ ] Migrate critical route files to Repository pattern (plans.py, payments.py, subscribers.py)
- [ ] APScheduler → separate worker/Redis queue

### P2
- [ ] Analytics Dashboard (Razorpay vs QR payments comparison)
- [ ] Object Storage migration (local files → S3/R2)
- [ ] telegram_webhook.py refactoring (~4300 lines → smaller handlers)

### P3
- [ ] WhatsApp integration
- [ ] Multi-language bot support
- [ ] CRA → Vite migration

## Known Issues
- Resend email OTP: Domain verification pending
- Production env vars need user injection on VPS
- telegram_webhook.py needs refactoring (~4300 lines)

## Production Deployment Notes
- Set `ENVIRONMENT=production` to enforce JWT_SECRET requirement
- Set `JWT_SECRET` (strong random value)
- Set `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`
- Super admin bootstrap runs at startup — no manual DB edits needed

## Test Reports
- Iteration 35: Tenant Management CRUD (23/23 passed)
- Iteration 36: Phase 1 Security Hardening (16/16 passed)
- Iteration 37: Phase 2+3 Impersonation + Risk Alerts (15/15 backend, 100% frontend)
