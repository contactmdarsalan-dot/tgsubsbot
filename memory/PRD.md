# TgSubsBot - Telegram Subscription Bot SaaS Platform

## Original Problem Statement
Transform a Telegram Subscription Bot into a scalable, market-ready SaaS product with multi-tenant isolation, RBAC, and enterprise-grade security.

## Core Requirements
1. Multi-Tenant SaaS isolation across database, backend, and webhooks
2. RBAC: Super Admins (platform) vs Tenant Admins (dashboard) vs Bot Admins (Telegram Mini App)
3. Security: JWT auth, CORS, Telegram initData HMAC verification, Audit Logging
4. AI-powered payment verification (GPT-5.2 Vision)
5. Telegram Bot with subscription management, payments, broadcasts, live sessions

## What's Been Implemented

### Phase 1-6: (Complete)
- Full Telegram bot, Plans CRUD, Payments, Subscribers, Mini App
- Multi-Tenant SaaS isolation with RBAC
- Security hardening (JWT, HMAC, Audit logs)
- Backend refactoring (monolith -> modular routes)
- Frontend refactoring + Rose/Crimson design system
- Super Admin sidebar isolation + UI fixes

### Phase 7: Trial Management (Complete - 2026-04-01)
- Trial Management System: 7 endpoints + UI tab in SaaSManagement.jsx
- All tested: Iteration 23 (19/19 passed)

### Phase 8: Super Admin Control Center + Tenant Profile (Complete - 2026-04-01)
- Control Center Dashboard with platform overview, revenue charts, top tenants
- Tenant Profile Page with 6 tabs (Overview, Subscribers, Payments, Plans, Admins, Config)
- All tested: Iteration 24 (12/12 passed)

### Phase 9: Dynamic Pricing + Team Management (Complete - 2026-04-02)
- Dynamic Pricing Plans on Landing Page
- Free Trial self-activation
- Tenant Team Management
- Login/Registration UI fixes
- All tested: Iterations 25-26

### Phase 10: P0 Tenant Data Isolation Fix (Complete - 2026-04-02)
- **CRITICAL SECURITY FIX**: Fixed tenant data leaking to other tenants
- Root cause: `get_user_tenant()` returned empty string for users without `tenant_id`, causing `tq()` to skip filtering → ALL data visible to unauthorized tenants
- Fix: `get_user_tenant()` now returns `"__no_tenant__"` for non-super-admin users without tenant_id
- Fix: `tenant_query()` in tenant.py now always filters (removed DEFAULT skip)
- Fix: Registration auto-creates unique tenant (`tenant_xxxxxxxxxxxx`) for every new user
- Fix: Free trial activation auto-creates tenant if user doesn't have one
- Fix: PDF export route now uses tenant filtering
- All tested: Iteration 27 (17/17 backend, all frontend passed)

## Architecture
```
/app/backend/
├── server.py               # App setup, CORS, file download
├── routes/
│   ├── admin.py            # Super Admin routes + Trial + Platform Stats + Tenant Profile
│   ├── auth.py             # Login, Registration (auto-tenant), Free Trial
│   ├── tenant.py           # Tenant Team Management
│   ├── dashboard.py        # Tenant analytics, settings, channels (tenant-filtered)
│   ├── plans.py, subscribers.py, payments.py (all tenant-filtered)
│   ├── analytics_exports.py, broadcasts.py, engagement.py
│   ├── live_content.py, miniapp_user.py, miniapp_admin.py, telegram_webhook.py
├── services/
│   ├── permissions.py      # CRITICAL: get_user_tenant(), tq() - tenant isolation
│   ├── tenant.py           # tenant_query(), DEFAULT_TENANT_ID
│   ├── auth.py, telegram.py, payment.py, chat_pool.py, background_tasks.py

/app/frontend/
├── src/
│   ├── App.js
│   ├── components/Layout.jsx  # RBAC sidebar
│   ├── pages/
│   │   ├── Dashboard.jsx      # SuperAdmin + Tenant dashboards
│   │   ├── TenantProfile.jsx  # 6-tab tenant deep-dive
│   │   ├── TeamManagement.jsx # Tenant owner admin management
│   │   ├── SaaSManagement.jsx # 5 tabs: Tenants, Admins, Subs, Trials, Plans
```

## Prioritized Backlog

### P1 (Next)
- [ ] Implement Impersonation Mode (Super Admin -> Tenant Admin login)
- [ ] Risk & Alerts System UI (Fraud detection, high refund alerts)

### P2
- [ ] Move APScheduler to separate worker/Redis queue
- [ ] Subscription Analytics Dashboard (MRR, churn, revenue graphs)

### P3
- [ ] WhatsApp integration
- [ ] Multi-language bot support

## 3rd Party Integrations
- OpenAI GPT-5.2 Vision (Emergent LLM Key) - Payment verification
- Razorpay - Online payments
- Telegram Bot API - Core bot functionality
- Resend (BLOCKED: domain verification pending) - Email OTPs

## Known Issues
- Resend email OTP: Domain verification pending by user
- Production env vars need user injection (MONGO_URL, JWT_SECRET, etc.)
