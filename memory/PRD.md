# TgSubsBot - Telegram Subscription Bot SaaS

## Original Problem Statement
Transform a Telegram Subscription Bot into a scalable, market-ready SaaS product. Features include a Telegram Mini App (WebApp), plans management, AI support chat, Referral System, Payment History, dual payment options (Razorpay and Manual UPI with QR), a dark "glassmorphism" UI, phone number login, and comprehensive Admin panels.

## Architecture
- **Frontend**: React + Framer Motion + Telegram WebApp SDK
- **Backend**: FastAPI + Motor (async MongoDB) + APScheduler
- **Database**: MongoDB with tenant isolation
- **AI**: OpenAI GPT-5.2 Vision (Payment Screenshot Verification via Emergent LLM Key)
- **Payments**: Razorpay (instant) + Manual UPI (QR + AI verify)
- **Email**: Resend (OTPs)

## Tenant Isolation (SaaS Multi-Tenant)
- All collections tagged with `tenant_id` field
- Default tenant: `"default"` for backwards compatibility
- `tenant_query()` utility scopes all DB queries per tenant
- Migration script: `/app/backend/scripts/migrate_tenant.py`
- Tenant CRUD: `/api/miniapp/admin/tenant/*`

## Key Collections (all with tenant_id)
- `tenants` - Creator/tenant registry
- `payments` - Payment records (Razorpay + UPI)
- `subscribers` - Active subscriptions
- `plans` - Subscription plans
- `bot_users` - Telegram bot users
- `paid_posts` - Paid content posts
- `live_sessions` - Live streaming sessions
- `live_tickets` - Live session tickets (with AI verification)
- `broadcasts` - Message broadcasts
- `miniapp_users` - Mini App registered users

## Completed Features
1. **Mini App UI** - Dark glassmorphism theme with pink accents
2. **Phone Login** - With 20% discount hook
3. **Plans Management** - Full CRUD with channel assignment
4. **Payment Options** - Razorpay + Manual UPI + QR auto-generation
5. **AI Screenshot Verify** - GPT-5.2 Vision for payment validation
6. **Admin Panel (MiniApp)** - Stats, Broadcasts, Live Sessions, Paid Posts, Users
7. **Live Sessions** - Create, Announce, Go Live, Ticket system
8. **Paid Posts** - Blur level control, unlock system
9. **Support AI Chat** - In-app AI support
10. **Referral System** - Code-based referrals
11. **Tenant Isolation (P0)** - Multi-tenant SaaS architecture ✅ (2026-03-31)
12. **AI Auto-Verify Live Tickets (P1)** - GPT-5.2 Vision for live ticket screenshots ✅ (2026-03-31)
13. **Live Tab for Users** - Public live sessions view with ticket purchase UI ✅ (2026-03-31)

## Key API Endpoints
- `POST /api/miniapp/upload-screenshot` - Plan payment screenshot + AI verify
- `POST /api/miniapp/live-ticket/upload-screenshot` - Live ticket screenshot + AI verify
- `GET /api/miniapp/live-sessions/public` - Public live sessions
- `GET /api/miniapp/live-ticket/status/{tg_id}/{session_id}` - Ticket status
- `GET /api/miniapp/admin/stats/{tg_id}` - Tenant-scoped admin stats
- `GET /api/miniapp/admin/tenant/{tg_id}` - Tenant info
- `POST /api/miniapp/admin/tenant/create` - Create new tenant

## Remaining Tasks
### P2
- Custom Domain mapping per SaaS tenant
- Resend Domain Verification (user action needed)
- Production Deployment Sync (Save to Github + Coolify redeploy)

### P3 (Future)
- WhatsApp integration
- Multi-language bot support
- MiniApp.jsx component refactoring (break into smaller components)

## Testing
- Iterations 10-14: All 100% passing
- Latest: Backend 16/16 (100%), Frontend 100%
