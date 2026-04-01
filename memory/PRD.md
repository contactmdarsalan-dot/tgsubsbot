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

### Phase 1: MVP (Complete)
- Full Telegram bot with subscription management
- Plans CRUD, Payments (manual + Razorpay), Subscribers management
- Telegram Mini App for user subscriptions
- Admin dashboard with analytics
- AI payment screenshot verification (GPT-5.2)

### Phase 2: Multi-Tenant SaaS (Complete)
- Tenant isolation with tenant_id on all data
- RBAC with centralized permissions (services/permissions.py)
- Tenant Admin onboarding (isolated dashboard)
- SaaS Management for Super Admins
- Data migration tool for legacy data
- Landing page with dark rose/crimson theme

### Phase 3: Security Hardening (Complete - 2026-03-31)
- **P0 Security**: Strict RBAC, JWT enforcement, MongoDB indexes, CORS, removed `is_admin` bypass, removed `DEFAULT_TENANT_ID` from writes
- **P1 Security**: Telegram `initData` HMAC-SHA256 verification, Audit logging, Pydantic Enums, Query limits
- All tested: Iteration 20 (P0, 29/29), Iteration 21 (P1, 39/39)

### Phase 4: Backend Refactoring (Complete - 2026-03-31)
- Split `core.py` (1513L) into: `plans.py`, `subscribers.py`, `payments.py`, `dashboard.py`
- Split `features.py` (2255L) into: `broadcasts.py`, `engagement.py`, `live_content.py`, `analytics_exports.py`
- Split `miniapp.py` (1690L) into: `miniapp_user.py`, `miniapp_admin.py`
- All tested: Iteration 22 (51/51 passed)

### Phase 5: Frontend Refactoring & Design System (Complete - 2026-03-31)
- Split `MiniApp.jsx` (1540L) into 6 subcomponents
- Rewrote `Layout.jsx` with RBAC-aware sidebar
- Migrated entire app from indigo/purple to rose/crimson theme

### Phase 6: Super Admin Sidebar + UI Fixes (Complete - 2026-04-01)
- Super Admin sidebar isolated to Platform pages only
- Tenant Admin Management with CRUD
- Login Page with registration + sign-in modes
- Button/Input text color fixes

### Phase 7: Trial Management + Object Storage (Complete - 2026-04-01)
- **Trial Management System**: 7 backend endpoints (GET/PUT /trial/config, GET /trial/accounts, POST /trial/activate, POST /trial/extend, POST /trial/cancel, POST /trial/convert)
- **Trial UI**: 5th "Trials" tab in SaaSManagement.jsx with stats cards, trial config summary, trial accounts table, activate trial for existing user, Trial Settings dialog, Convert Trial to Paid dialog
- **Object Storage Migration**: All 6 upload points migrated from local disk to Emergent Object Storage (dashboard.py, miniapp_user.py, miniapp_admin.py)
- **Storage Service**: `/app/backend/services/storage.py` with init_storage(), upload_file(), put_object(), get_object() + local fallback
- **File Download**: `/api/files/{path}` endpoint for serving cloud-stored files
- **Backward Compat**: Old `/api/uploads/` URLs still work for existing local files
- All tested: Iteration 23 (19/19 passed)

## Architecture

```
/app/backend/
├── server.py               # App setup, CORS, object storage init, file download endpoint
├── config.py               # Environment config
├── database.py             # MongoDB connection + cache
├── models/                 # Pydantic models with Enums
├── routes/
│   ├── auth.py             # Login, registration
│   ├── admin.py            # Super Admin routes + Trial Management (7 endpoints)
│   ├── plans.py            # Plans CRUD
│   ├── subscribers.py      # Subscribers + bulk
│   ├── payments.py         # Payments + Razorpay + bulk
│   ├── dashboard.py        # Settings + Channels + Analytics + File Uploads (cloud)
│   ├── broadcasts.py       # Templates + Broadcasts + Scheduled
│   ├── engagement.py       # Coupons + Tags + Referrals + FAQs
│   ├── live_content.py     # Live + Creators + Paid Posts
│   ├── analytics_exports.py# Revenue + Exports + Chat Tracking
│   ├── miniapp_user.py     # MiniApp user endpoints (uploads migrated to cloud)
│   ├── miniapp_admin.py    # MiniApp admin endpoints (uploads migrated to cloud)
│   ├── telegram_webhook.py # Bot webhook handler
│   └── tenant.py           # Creator onboarding
├── services/
│   ├── storage.py          # Emergent Object Storage service (NEW)
│   ├── permissions.py      # Centralized RBAC
│   ├── audit.py            # Action logging
│   ├── telegram_verify.py  # HMAC-SHA256 validator
│   ├── telegram.py         # Telegram API helpers
│   ├── payment.py          # AI screenshot analysis
│   ├── chat_pool.py        # Chat group management
│   └── background_tasks.py # Scheduled jobs
/app/frontend/
├── src/
│   ├── components/Layout.jsx  # RBAC-aware sidebar
│   ├── pages/
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
- Emergent Object Storage - File uploads (NEW, using EMERGENT_LLM_KEY)
- Resend (BLOCKED: domain verification pending) - Email OTPs

## Known Issues
- Resend email OTP: Domain verification pending by user
- Production env vars need user injection (MONGO_URL, JWT_SECRET, etc.)
