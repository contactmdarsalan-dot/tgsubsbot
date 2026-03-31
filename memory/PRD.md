# TgSubsBot - Telegram Subscription Bot SaaS

## Original Problem Statement
Transform a Telegram Subscription Bot into a scalable, market-ready SaaS product with Telegram Mini App, plans management, AI support chat, Referral System, Payment History, dual payment options (Razorpay and Manual UPI with QR), a dark "glassmorphism" UI, phone number login, comprehensive Admin panels for Paid Posts/Live Sessions, and a multi-tenant creator SaaS architecture.

## Architecture
- Frontend: React + Framer Motion + Telegram WebApp SDK
- Backend: FastAPI + Motor (async MongoDB) + APScheduler
- Database: MongoDB with tenant isolation (tenant_id on all collections)
- AI: OpenAI GPT-5.2 Vision (Payment Screenshot Verification)
- Payments: Razorpay (instant) + Manual UPI (QR + AI verify)

## Roles
- **Super Admin**: Manages entire SaaS platform (tenants, bot plans, all data)
- **Tenant Admin**: Web dashboard login, sees only their tenant's data (subscribers, payments, plans, broadcasts etc.)
- **Bot Admin**: Telegram Mini App admin (TG User ID based, manages bot features)
- **User**: Regular subscriber

## All Completed Features
1. Mini App UI - Dark glassmorphism theme
2. Phone Login with discount hook
3. Plans Management with full CRUD
4. Razorpay + Manual UPI + QR auto-generation
5. AI Screenshot Verify (GPT-5.2 Vision)
6. Admin Panel - Stats, Broadcasts, Live, Paid Posts, Users
7. Live Sessions - Create, Announce, Go Live, End, Delete
8. Paid Posts - Blur control, unlock, Image/Video upload
9. AI Support Chat
10. Referral System
11. Tenant Isolation (multi-tenant SaaS)
12. AI Auto-Verify Live Tickets
13. Creator Self-Service Onboarding (/creator-onboard)
14. Creator Dashboard (/creator-dashboard)
15. SaaS Landing Page (/) - Dark rose/crimson with dynamic pricing
16. Extend Subscription + 3-day expiry warning
17. SaaS Management (/dashboard/saas-management) - Bot Plans CRUD + Tenant CRUD
18. Data Migration API + Quick Setup button
19. Landing page Dashboard button for logged-in users
20. **Tenant Admin System** - Create tenant admin users (email/password) who login to web dashboard and see only their tenant's data
21. **Dashboard Tenant Filtering** - Plans, Subscribers, Payments, Analytics, Broadcasts, Live Sessions, Referrals, Coupons, TG Admins all filtered by tenant_id
22. **Admin Dialog** - Dual sections: Bot Admins (TG) + Dashboard Admins (Web) with create/remove
23. **Permissions System** - 8 toggleable permissions for bot admins

## Tenants
- **Anamika** (tenant_85ee971d0285): Production data
- **Kaloo** (default): Empty, ready for new bot

## Remaining Tasks
- (P2) Subscription Analytics (Revenue graph, churn rate, MRR dashboard)
- (P2) Resend domain verification (Email OTPs - blocked on user action)
- (P2) Production deployment sync ("Save to Github" + Coolify redeploy)
- (P3) WhatsApp integration
- (P3) Multi-language bot support
- (P3) MiniApp.jsx refactoring (1400+ lines)
