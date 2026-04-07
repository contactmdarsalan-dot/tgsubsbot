# CHANGELOG — TgSubsBot

## Phase 23: Impersonation Mode + Risk & Alerts + Route Guards (2026-04-07)
- **Impersonation Mode**: Super Admin can login as any Tenant Admin via purple eye button
  - Backend: POST /api/saas/impersonate/{tenant_id}, GET /api/saas/impersonation-log
  - Frontend: Impersonate button in tenant table, amber banner with "Exit Impersonation"
  - Full audit trail in audit_logs collection
- **Risk & Alerts System**: 5 alert detection types (high_refund_rate, failed_payments_spike, abandoned_bot, unusual_volume, expiry_wave)
  - Backend: GET /api/saas/risk-alerts, POST /api/saas/risk-alerts/{id}/dismiss
  - Frontend: RiskAlerts.jsx with stats cards, severity filters, search, dismiss
- **Frontend Role-Based Route Guards**: SuperAdminRoute, TenantRoute wrappers in App.js
  - Super Admin pages: saas-management, risk-alerts, admin-subs, user-management, branding
  - Tenant pages: plans, subscribers, payments, broadcast, coupons, etc.
- **Layout.jsx email bypass removed**: Sidebar now uses role-only auth
- **Tested**: 15/15 backend + 100% frontend (iteration_37.json)

## Phase 22: Production Security Hardening (2026-04-07)
- JWT enhanced with role + tenant_id in payload
- Email-based super admin bypass removed from ALL files (permissions.py, admin.py, auth.py, tenant.py)
- JWT_SECRET production guard (crash if missing in production)
- Super Admin Bootstrap at startup
- RequestContext Middleware (X-Request-ID)
- Compound indexes (tenant_id, id) on 12 collections
- Repository pattern base class (TenantScopedRepository)
- Fixed is_super_admin shadowing bug in auth.py
- Fixed duplicate function name in admin.py
- Enhanced audit service with before/after state
- Tested: 16/16 (iteration_36.json)

## Phase 21: Critical Multi-Tenant Data Isolation Fix (2026-04-05)
- Added tenant_id filter to 50+ DB queries in telegram_webhook.py and miniapp_user.py

## Phase 20: Enhanced Tenant Management (2026-04-05)
- Complete CRUD with Change Owner, Permanent Delete, Reactivate, Isolation Report

## Phase 19: Razorpay Bot Payment Integration (2026-04-04)
- Razorpay Payment Links in Telegram Bot flow

## Phase 18: Telegram Bot Command Fix (2026-04-04)
- Fixed /start command URL button validation
