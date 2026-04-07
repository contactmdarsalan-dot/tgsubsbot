# TgSubsBot - Product Requirements Document

## Original Problem Statement
Transforming a Telegram Subscription Bot into a scalable, market-ready SaaS product with full multi-tenant isolation, distinct RBAC, and production-grade security.

## Security Model (Production-Hardened)
- **JWT**: Includes `user_id`, `role`, `tenant_id`. Secret MUST be set in production (`ENVIRONMENT=production`)
- **RBAC**: Role-based only — no email-based bypass anywhere (frontend + backend)
- **Route Guards**: `SuperAdminRoute`, `TenantRoute`, `ProtectedRoute` in frontend
- **Tenant Isolation**: Repository pattern (`TenantScopedRepository`) + `tq()` helper
- **Dead Filter**: `DEFAULT_TENANT_ID = "__unresolved_tenant__"` — unresolved tenant queries match NOTHING
- **Impersonation**: Full audit trail, original token preserved for safe exit
- **Request Tracing**: `X-Request-ID` header on every response via middleware
- **Compound Indexes**: `(tenant_id, id)` on all 12 business collections

## Architecture Summary
```
Backend:
├── repositories/base.py    → TenantScopedRepository (mandatory isolation)
├── services/permissions.py → Role-only RBAC
├── services/tenant.py      → No default fallback
├── server.py               → RequestContext middleware + bootstrap
├── routes/plans.py         → Repository pattern (plans_repo)
├── routes/subscribers.py   → Repository pattern (subscribers_repo)
├── routes/payments.py      → Direct tenant resolution
├── routes/admin.py         → Impersonation + Risk Alerts

Frontend:
├── App.js                  → SuperAdminRoute, TenantRoute guards
├── Layout.jsx              → Role-only sidebar, impersonation banner
├── RiskAlerts.jsx           → Fraud detection UI
├── SaaSManagement.jsx      → Impersonate button
```

## Completed (All Tested)
- [x] Phase 22: Security Hardening (JWT, RBAC, email bypass removal)
- [x] Phase 23: Impersonation + Risk & Alerts + Route Guards
- [x] Phase 24: Default tenant removal + Repository pattern migration

## Prioritized Backlog

### P1 (Next)
- [ ] APScheduler → separate worker/Redis queue
- [ ] Migrate remaining route files to Repository pattern (dashboard.py, broadcasts.py, etc.)

### P2
- [ ] Analytics Dashboard (Razorpay vs QR payments comparison)
- [ ] Object Storage migration (local files → S3/R2)
- [ ] telegram_webhook.py refactoring (~4300 lines → smaller handlers)

### P3
- [ ] WhatsApp integration
- [ ] Multi-language bot support
- [ ] CRA → Vite migration

## Test Reports
- Iteration 35: Tenant Management CRUD (23/23 passed)
- Iteration 36: Phase 22 Security Hardening (16/16 passed)
- Iteration 37: Phase 23 Impersonation + Alerts (15/15 + frontend)
- Iteration 38: Phase 24 Repository Migration (18/18 + frontend)
