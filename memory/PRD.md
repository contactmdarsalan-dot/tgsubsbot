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

### Phase 1-6: (Complete - see CHANGELOG.md for details)
- Full Telegram bot, Plans CRUD, Payments, Subscribers, Mini App
- Multi-Tenant SaaS isolation with RBAC
- Security hardening (JWT, HMAC, Audit logs)
- Backend refactoring (monolith → modular routes)
- Frontend refactoring + Rose/Crimson design system
- Super Admin sidebar isolation + UI fixes

### Phase 7: Trial Management + Object Storage (Complete - 2026-04-01)
- Trial Management System: 7 endpoints + UI tab in SaaSManagement.jsx
- Object Storage Migration: 6 upload points → Emergent Object Storage
- All tested: Iteration 23 (19/19 passed)

### Phase 8: Super Admin Control Center + Tenant Profile (Complete - 2026-04-01)
- **Control Center Dashboard**: Rewrote Dashboard.jsx for Super Admin with:
  - Platform Overview (Total Tenants, Tenant Admins, Platform Revenue, Pending Requests)
  - Bot Ecosystem (Total Bot Users, Active Subscribers, Tenant Revenue, Payments)
  - Revenue Trend chart (14 days across all tenants)
  - Top Tenants ranking by revenue (clickable → Tenant Profile)
  - Recent Tenants + Recent Subscriptions activity feed
  - Trial Status card + Quick Links (Analytics, Revenue)
- **Tenant Profile Page**: New `/dashboard/tenant/:tenantId` route with:
  - 8 stat blocks (Revenue, Bot Users, Active Subs, Payments, Plans, Broadcasts, Dashboard Admins, TG Admins)
  - 6 tabs: Overview (revenue chart + plan distribution), Subscribers, Payments, Plans, Admins, Config
  - Sensitive data blurring (bot token, razorpay key)
  - Copy-to-clipboard tenant ID
- **Backend APIs**: Enhanced `/api/admin/stats` with comprehensive platform data + new `/api/admin/tenant-profile/{tenant_id}`
- **RBAC**: Super Admin → Control Center, Tenant Admin → normal Dashboard
- All tested: Iteration 24 (12/12 passed)

## Architecture
```
/app/backend/
├── server.py               # App setup, CORS, object storage, file download
├── routes/
│   ├── admin.py            # Super Admin routes + Trial + Platform Stats + Tenant Profile
│   ├── auth.py, plans.py, subscribers.py, payments.py, dashboard.py
│   ├── broadcasts.py, engagement.py, live_content.py, analytics_exports.py
│   ├── miniapp_user.py, miniapp_admin.py, telegram_webhook.py, tenant.py
├── services/
│   ├── storage.py          # Emergent Object Storage
│   ├── permissions.py, audit.py, telegram_verify.py, telegram.py
│   ├── payment.py, chat_pool.py, background_tasks.py

/app/frontend/
├── src/
│   ├── App.js              # Routes including /dashboard/tenant/:tenantId
│   ├── components/Layout.jsx  # RBAC sidebar
│   ├── pages/
│   │   ├── Dashboard.jsx      # SuperAdminDashboard + TenantDashboard (role-based)
│   │   ├── TenantProfile.jsx  # 6-tab tenant deep-dive
│   │   ├── SaaSManagement.jsx # 5 tabs: Tenants, Admins, Subs, Trials, Plans
│   │   └── ... (other pages)
```

## Prioritized Backlog

### P1 (Next)
- [ ] Implement Impersonation Mode (Super Admin → Tenant Admin login)
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
- Emergent Object Storage - File uploads (using EMERGENT_LLM_KEY)
- Resend (BLOCKED: domain verification pending) - Email OTPs

## Known Issues
- Resend email OTP: Domain verification pending by user
- Production env vars need user injection (MONGO_URL, JWT_SECRET, etc.)
