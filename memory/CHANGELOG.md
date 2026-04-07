# CHANGELOG — TgSubsBot

## Phase 24: Default Tenant Removal + Repository Pattern Migration (2026-04-07)
- **Default tenant eliminated**: Migrated "Kaloo" from `tenant_id: "default"` to `tenant_b36ca1244502`
- **DEFAULT_TENANT_ID = `"__unresolved_tenant__"`**: Dead filter that matches nothing — prevents any data leak from unresolved tenants
- **`get_or_create_default_tenant()` removed**: No more auto-creating default tenant
- **plans.py fully rewritten**: Uses `plans_repo` (TenantScopedRepository) for all CRUD — `find_many()` for tenant-scoped, `find_many_global()` for super admin
- **subscribers.py fully rewritten**: Uses `subscribers_repo.insert_one()` for creates, `tq()` for reads
- **payments.py cleaned**: Removed `DEFAULT_TENANT_ID` import, uses direct plan tenant resolution
- **dashboard.py, broadcasts.py cleaned**: Removed unused `DEFAULT_TENANT_ID` imports
- **Tested**: 18/18 backend + 100% frontend (iteration_38.json)

## Phase 23: Impersonation Mode + Risk & Alerts + Route Guards (2026-04-07)
- Impersonation Mode: Super Admin → Tenant Admin (audit-logged)
- Risk & Alerts: 5 detection types (refund rate, failed spike, abandoned bot, volume, expiry)
- Frontend SuperAdminRoute + TenantRoute guards
- Layout.jsx email bypass removed
- Tested: 15/15 backend + 100% frontend (iteration_37.json)

## Phase 22: Production Security Hardening (2026-04-07)
- JWT with role/tenant_id, email bypass removed, compound indexes
- Tested: 16/16 (iteration_36.json)

## Phase 21: Critical Multi-Tenant Data Isolation Fix (2026-04-05)
## Phase 20: Enhanced Tenant Management (2026-04-05)
## Phase 19: Razorpay Bot Payment Integration (2026-04-04)
## Phase 18: Telegram Bot Command Fix (2026-04-04)
