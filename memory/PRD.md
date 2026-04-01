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
- **P1 Security**: Telegram `initData` HMAC-SHA256 verification (`services/telegram_verify.py`), Audit logging (`services/audit.py`), Pydantic Enums, Query limits
- All tested: Iteration 20 (P0, 29/29), Iteration 21 (P1, 39/39)

### Phase 6: Super Admin Sidebar Separation + UI Fixes (Complete - 2026-04-01)
- **Super Admin Sidebar**: Removed all Tenant Admin operations (Plans, Subscribers, Payments etc.) from Super Admin sidebar. Super Admin now sees ONLY Platform pages: Overview, Tenants, Revenue, Analytics, Subscriptions, Support, Users, Platform Settings
- **Tenant Admin Management**: Added "Tenant Admins" tab to SaaS Management page showing all dashboard admins across tenants with remove capability
- **Login Page Fix**: Added `btn-romance` and `text-gradient-romance` CSS classes for rose gradient buttons and text
- **Button/Input Fix**: Fixed white text on outline/ghost buttons and input fields by adding explicit `text-foreground` class
- **Build Fixes**: `CI=false` in build script, lodash pinned to 4.17.21, yarn.lock tracked in git, `.env` properly in `.gitignore`

### Phase 5: Frontend Refactoring & Design System (Complete - 2026-03-31)
- Split `MiniApp.jsx` (1540L) into 6 subcomponents: `PlansScreen.jsx`, `StatusScreen.jsx`, `SupportScreen.jsx`, `ReferralScreen.jsx`, `AdminPanel.jsx`, `context.js` in `/pages/miniapp/`
- Rewrote `Layout.jsx` with RBAC-aware sidebar (Platform + Operations sections for Super Admin)
- Rewrote `Dashboard.jsx` as "Control Center" overview with metric cards, revenue chart, plan distribution
- **Design System Change**: Migrated entire app from indigo/purple (#6366F1) to rose/crimson (#E11D48) theme matching the landing page

### Phase 4: Backend Refactoring (Complete - 2026-03-31)
- Split `core.py` (1513L) into: `plans.py`, `subscribers.py`, `payments.py`, `dashboard.py`
- Split `features.py` (2255L) into: `broadcasts.py`, `engagement.py`, `live_content.py`, `analytics_exports.py`
- Split `miniapp.py` (1690L) into: `miniapp_user.py`, `miniapp_admin.py`
- **Result**: 3 giant files (5458L) → 10 domain files (4623L), removed 835 lines of dead code
- All tested: Iteration 22 (51/51 passed)

  - Updated: `index.css` CSS variables, `Layout.jsx`, `Dashboard.jsx`, `MiniApp.jsx`, all miniapp subcomponents, `BotCheckout.jsx`, `design_guidelines.json`
  - Consistent rose/crimson across: Landing page, Login, Dashboard, Revenue, MiniApp

## Architecture

```
/app/backend/
├── server.py               # App setup, CORS, router inclusion
├── config.py               # Environment config
├── database.py             # MongoDB connection + cache
├── models/                 # Pydantic models with Enums
├── routes/
│   ├── auth.py             # Login, registration
│   ├── admin.py            # Super Admin routes
│   ├── plans.py            # Plans CRUD (74L)
│   ├── subscribers.py      # Subscribers + bulk (281L)
│   ├── payments.py         # Payments + Razorpay + bulk (516L)
│   ├── dashboard.py        # Settings + Channels + Analytics + Branding (596L)
│   ├── broadcasts.py       # Templates + Broadcasts + Scheduled (466L)
│   ├── engagement.py       # Coupons + Tags + Referrals + FAQs (424L)
│   ├── live_content.py     # Live + Creators + Paid Posts (646L)
│   ├── analytics_exports.py# Revenue + Exports + Chat Tracking (324L)
│   ├── miniapp_user.py     # MiniApp user endpoints (770L)
│   ├── miniapp_admin.py    # MiniApp admin endpoints (526L)
│   ├── telegram_webhook.py # Bot webhook handler
│   └── tenant.py           # Creator onboarding
├── services/
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
│   │   ├── MiniApp.jsx        # Telegram Mini App (1540L - needs refactoring)
│   │   ├── SaaSManagement.jsx # Platform management
│   │   └── ... (other pages)
```

## Prioritized Backlog

### P1 (Next)
- [ ] Implement remaining Super Admin pages with updated design
- [ ] Impersonation Mode (Super Admin → Tenant Admin login)

### P2
- [ ] Object Storage migration (local uploads → S3/Cloudflare R2)
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
- Design system updated from indigo/purple to rose/crimson (matching landing page) on 2026-03-31
