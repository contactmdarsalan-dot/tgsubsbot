# TgSubsBot - Telegram Subscription Bot SaaS Platform

## Original Problem Statement
Transform a Telegram Subscription Bot into a scalable, market-ready SaaS product with multi-tenant isolation, RBAC, and enterprise-grade security.

## Core Requirements
1. Multi-Tenant SaaS isolation across ALL database collections, backend routes, and webhooks
2. RBAC: Super Admins (platform) vs Tenant Admins/Owners (dashboard) vs Bot Admins (Telegram)
3. Security: JWT auth, CORS, Telegram initData HMAC, tenant data isolation
4. AI-powered payment verification (GPT-5.2 Vision)
5. Telegram Bot with subscription management, payments, broadcasts, live sessions

## What's Been Implemented

### Phase 1-9: (Complete - see CHANGELOG.md for details)
- Full Telegram bot, Plans CRUD, Payments, Subscribers, Mini App
- Multi-Tenant SaaS with RBAC, Trial Management, Team Management
- Super Admin Control Center, Tenant Profile, Dynamic Pricing
- Rose/Crimson design system, Login/Registration UI fixes

### Phase 10: P0 Core Tenant Isolation (Complete - 2026-04-02)
- Fixed `get_user_tenant()` to return `__no_tenant__` for users without tenant_id
- Fixed `tenant_query()` to always filter (no DEFAULT skip)
- Registration auto-creates unique tenant per user

### Phase 11: Payments & Subscribers Pagination (Complete - 2026-04-02)
- Server-side pagination with page/limit/search params
- Server-side stats (total_collected, pending_count, total_transactions)
- MongoDB aggregation for revenue (removed `.to_list(10000)`)

### Phase 12: COMPLETE Data Isolation + UI Fixes (Complete - 2026-04-02)
- **20+ route files** updated with tenant isolation:
  - `live_content.py`: Creators, TG Admins, Live Sessions, Paid Posts, Super Chats, Live Tickets, Unlock Requests
  - `engagement.py`: Coupons, FAQs, Referrals, Video Calls, Tags, Blocked Users, User Notes
  - `broadcasts.py`: Templates, Broadcasts, Scheduled Broadcasts, Renewal Broadcasts
  - `dashboard.py`: Channels, Chat Groups, Chat Sessions, Settings, Bot Language
  - `analytics_exports.py`: Bot Activity logs and stats
  - `admin.py`: Mini App Users restricted to Super Admin only
- **Plans Dialog UI**: Widened to 550px with scrollable content
- **Sidebar**: Mini App Users moved to Super Admin only
- **Settings**: Tenant-isolated (each tenant gets own settings document)
- **Data Migration API**: `/api/saas/migrate-to-tenant` for normalizing old data
- Tested: Iteration 30 (ALL PASSED - 21 routes verified for new tenant = 0 data, original tenant correct)

### Phase 13: MiniApp Admin/User Final Isolation (Complete - 2026-04-02)
- **8 critical security fixes in `miniapp_admin.py`**:
  - `/admin/payment-action`: Payment update, plan lookup, subscriber upsert now use `tenant_query()`
  - `/admin/announce-live`: Session find + update now tenant-scoped
  - `/admin/paid-post/{id}/toggle`: Post find + update now tenant-scoped
  - `/admin/paid-post/{id}/blur`: Update now tenant-scoped
  - `/admin/paid-post/{id}/broadcast`: Post find now tenant-scoped
  - `/admin/live-session/{id}/go-live`: Session find + update now tenant-scoped
  - DELETE `/admin/live-session/{id}`: Delete now tenant-scoped
  - `/admin/live-session/{id}/end`: Update now tenant-scoped
- **`miniapp_user.py` fixes**: upload-screenshot uses bot_user's tenant_id instead of hardcoded DEFAULT
- Tested: Iteration 31 (ALL 24 TESTS PASSED - cross-tenant access fully blocked)

### Phase 14: Mini App Tenant Resolution Fix (Complete - 2026-04-02)
- **Root cause**: Mini App frontend was NOT passing tenant_id to ANY backend API calls → all queries defaulted to "default" tenant which had 0 plans
- **New endpoint**: `/api/miniapp/resolve-tenant/{userId}` - 3-step smart fallback: bot_users → settings → first tenant with active plans
- **Frontend fixes**: MiniApp.jsx, PlansScreen.jsx, ReferralScreen.jsx, SupportScreen.jsx all now pass tenant_id
- **Webhook fix**: telegram_webhook.py - 15+ `DEFAULT_TENANT_ID` usages replaced with `bot_tenant_id` resolved from settings
- **Settings fix**: dashboard.py settings update now persists `tenant_id` in settings document
- Tested: Iteration 32 (ALL TESTS PASSED - 8 plans show in Mini App matching Dashboard)

## Architecture
```
/app/backend/
├── server.py
├── routes/ (ALL routes tenant-isolated)
│   ├── admin.py (Super Admin + Trial + Stats + Migration)
│   ├── auth.py (Login, Registration with auto-tenant)
│   ├── tenant.py (Team Management)
│   ├── dashboard.py (Analytics, Settings, Channels, Groups)
│   ├── payments.py (Paginated, tenant-filtered)
│   ├── subscribers.py (Paginated, tenant-filtered)
│   ├── plans.py, live_content.py, engagement.py, broadcasts.py
│   ├── analytics_exports.py, miniapp_user.py, miniapp_admin.py
├── services/
│   ├── permissions.py (CRITICAL: get_user_tenant(), tq())
│   ├── tenant.py (tenant_query(), DEFAULT_TENANT_ID)
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

## Production Deployment Notes
- **IMPORTANT**: After deploying, run the data migration endpoint:
  `POST /api/saas/migrate-to-tenant` with `{"source_tenant_id": "default", "target_tenant_id": "<actual_tenant_id>"}`
  to normalize old data with `tenant_id: "default"` to the correct tenant.
- Ensure original creator's user record has correct `tenant_id` and `role: "tenant_owner"`
- All new users auto-get unique `tenant_id` on registration

## 3rd Party Integrations
- OpenAI GPT-5.2 Vision (Emergent LLM Key)
- Razorpay, Telegram Bot API
- Resend (BLOCKED: domain verification pending)

## Known Issues
- Resend email OTP: Domain verification pending
- Production env vars need user injection
