# TgSubsBot - Product Requirements Document

## Original Problem Statement
Transforming a Telegram Subscription Bot into a scalable, market-ready SaaS product. Core requirements include full Multi-Tenant SaaS isolation, distinct RBAC (Super Admin vs. Tenant Admin), dynamic subscription plans, a highly analytical "Control Center" Super Admin Dashboard, and a conversion-focused Landing Page & Mini App.

## Core Requirements
1. Full Multi-Tenant SaaS isolation across database, backend, and webhooks
2. Distinct RBAC: Super Admins vs. Tenant Admins vs. Bot Admins
3. Razorpay integration for Telegram Bot checkout flows
4. "Global Marketplace App" API integration (Wallet, Coins, Revenue Share)
5. Comprehensive Tenant Management via Super Admin Dashboard

## User Personas
- **Super Admin**: Platform owner, manages all tenants, views global analytics
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
│   ├── server.py (FastAPI app, middleware, router mounting, startup bootstrap)
│   ├── config.py (Environment config, JWT_SECRET with production guard)
│   ├── database.py (MongoDB connection, compound indexes)
│   ├── repositories/
│   │   └── base.py (TenantScopedRepository — mandatory tenant isolation layer)
│   ├── services/
│   │   ├── auth.py (JWT with role/tenant_id in payload)
│   │   ├── permissions.py (Role-only RBAC, no email bypass)
│   │   ├── tenant.py (Tenant resolution, isolation utilities)
│   │   └── audit.py (Enhanced audit logging with before/after state)
│   ├── routes/
│   │   ├── auth.py, admin.py, plans.py, payments.py, subscribers.py
│   │   ├── telegram_webhook.py (~4300 lines, tenant-isolated)
│   │   ├── miniapp_user.py, miniapp_admin.py
│   │   ├── razorpay_webhook.py, global_app.py, global_wallet.py
│   │   └── tenant.py, dashboard.py, broadcasts.py, etc.
├── frontend/
│   ├── src/
│   │   ├── pages/ (LandingPage, Login, Dashboard, SaaSManagement, etc.)
│   │   ├── components/ (Layout with RBAC sidebar)
│   │   └── components/ui/ (Shadcn components, dark mode enforced)
```

## Security Model (Production-Hardened — Phase 22)
- **JWT**: Includes `user_id`, `role`, `tenant_id` in payload. Secret MUST be set in production.
- **RBAC**: Role-based only (`super_admin`, `tenant_owner`, `tenant_admin`, `admin`). No email-based bypass.
- **Tenant Isolation**: `tq()` helper + Repository pattern for mandatory tenant_id filtering.
- **Super Admin Bootstrap**: Startup ensures SUPER_ADMIN_EMAILS users have `role='super_admin'` in DB.
- **Request Tracing**: X-Request-ID header on every response via middleware.
- **Compound Indexes**: `(tenant_id, id)` on all business collections.
- **Audit Logging**: Enhanced with before/after state, request_id tracking.

## Prioritized Backlog

### P0 (Immediate)
- [x] Phase 1 Security Hardening (JWT, RBAC, email bypass removal) — DONE
- [ ] Phase 2: Migrate critical route files to use Repository pattern
- [ ] Phase 3: Frontend role-based route segmentation

### P1 (Next)
- [ ] Impersonation Mode (Super Admin → Tenant Admin login)
- [ ] Risk & Alerts System UI (Fraud detection, high refund alerts)
- [ ] Remove "default" tenant fallback entirely (after data backfill)

### P2
- [ ] Move APScheduler to separate worker/Redis queue
- [ ] Analytics Dashboard (Razorpay vs QR payments comparison)
- [ ] Object Storage migration (local files → S3/R2)

### P3
- [ ] WhatsApp integration
- [ ] Multi-language bot support
- [ ] CRA → Vite migration

## Known Issues
- Resend email OTP: Domain verification pending
- Production env vars need user injection on VPS
- `telegram_webhook.py` (~4300 lines) needs refactoring into smaller handlers

## Production Deployment Notes
- Set `ENVIRONMENT=production` to enforce JWT_SECRET requirement
- Set `JWT_SECRET` (strong random value)
- Set `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`
- Super admin bootstrap runs at startup — no manual DB edits needed
