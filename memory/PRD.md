# TgSubsBot - Telegram Subscription Bot SaaS

## Original Problem Statement
Transform a Telegram Subscription Bot into a scalable, market-ready SaaS product with multi-tenant architecture.

## Architecture
- Frontend: React + Framer Motion + Telegram WebApp SDK
- Backend: FastAPI + Motor (async MongoDB) + APScheduler
- Database: MongoDB with tenant isolation (tenant_id on all collections)
- AI: OpenAI GPT-5.2 Vision (Payment Screenshot Verification)

## Security Architecture
- JWT auth with no fallback secret (hard fail if missing)
- Centralized permissions service (`services/permissions.py`)
- Role-based access: super_admin, tenant_owner, tenant_admin, admin, customer
- SUPER_ADMIN_EMAILS env-driven allowlist
- All tenant routes require JWT + tenant access verification
- CORS strict allowlist (tgsubsbot.com + preview domain)
- MongoDB compound indexes on (tenant_id, status), (tenant_id, telegram_user_id)
- Frontend auth state from backend `/auth/me` only (no localStorage guessing)

## Roles & Access
- **Super Admin**: Platform section + all Operations + cross-tenant data
- **Tenant Admin**: Operations only + own tenant data only
- **Bot Admin**: Telegram Mini App admin panel (TG User ID based)

## Completed Features (25)
1-19. Core features (Mini App, Plans, Payments, AI Verify, Live, Paid Posts, etc.)
20. Tenant Admin System
21. Dashboard Tenant Filtering
22. SaaS Management + Data Migration
23. Landing Page with Pricing
24. **P0 Security Hardening Round 1**: verify_super_admin strict, CORS, tenant auth, indexes
25. **P0 Security Hardening Round 2**: Centralized permissions, remove is_admin bypass, /auth/me cleanup, branding protection

## Security Fixes Completed
- ✅ JWT_SECRET with warning if not set (dev fallback only)
- ✅ verify_super_admin() — role=="super_admin" or email in SUPER_ADMIN_EMAILS only
- ✅ Removed is_admin bypass from all super admin checks
- ✅ All /tenant/* routes require JWT auth
- ✅ Object-level tenant_id authorization on writes
- ✅ CORS strict allowlist
- ✅ MongoDB indexes at startup
- ✅ Frontend: removed localStorage admin guessing
- ✅ Centralized services/permissions.py
- ✅ Branding route protected (super_admin only)
- ✅ Payment delete/bulk-delete uses role check

## Remaining Security Items (P1)
- Telegram WebApp init data verification (miniapp routes)
- Pagination on large queries (.to_list(10000) → paginated)
- Encrypt sensitive tenant credentials (bot tokens)
- Rate limiting on auth endpoints
- Audit logs collection
- File upload validation (MIME type, size)

## Remaining Feature Tasks
- (P2) Subscription Analytics Dashboard
- (P2) Resend domain verification
- (P3) WhatsApp integration
- (P3) Multi-language bot support
- (P3) Route file splitting (core.py 1500L, features.py 2200L, miniapp.py 1600L)
- (P3) Frontend file splitting (MiniApp.jsx 1400L)
