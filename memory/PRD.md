# TgSubsBot - Telegram Subscription Bot SaaS

## Original Problem Statement
Transform a Telegram Subscription Bot into a scalable, market-ready SaaS product with Telegram Mini App, plans management, AI support chat, Referral System, Payment History, dual payment options (Razorpay and Manual UPI with QR), a dark "glassmorphism" UI, phone number login, comprehensive Admin panels for Paid Posts/Live Sessions, and a multi-tenant creator SaaS architecture.

## Architecture
- Frontend: React + Framer Motion + Telegram WebApp SDK
- Backend: FastAPI + Motor (async MongoDB) + APScheduler
- Database: MongoDB with tenant isolation (tenant_id on all collections)
- AI: OpenAI GPT-5.2 Vision (Payment Screenshot Verification)
- Payments: Razorpay (instant) + Manual UPI (QR + AI verify)

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
13. Live Tab for Users (public sessions + ticket purchase)
14. Creator Self-Service Onboarding (/creator-onboard)
15. Creator Dashboard (/creator-dashboard)
16. SaaS Landing Page (/) - Dark rose/crimson color palette
17. **Extend Subscription** - Active users see "Extend Subscription" with +days logic
18. **Expiry Warning** - Yellow warning banner when 3 days or less remain
19. **Live Management Fixes** - End Stream, Delete, descriptions, metadata tags
20. **SaaS Management Page** (/dashboard/saas-management) - Bot Plans CRUD with Feature Lists + Tenant CRUD + Admin Assignment
21. **Data Migration** - All 520 docs migrated from "default" to "Anamika" (tenant_85ee971d0285)
22. **Landing Page Pricing** - Dynamic pricing section fetching from /api/dashboard-plans
23. **Project Color Palette** - Landing page updated to dark rose/crimson (hsl(346,80%,50%))

## Tenants
- **Anamika** (tenant_85ee971d0285): 12 users, 46 subscribers, 185 payments, ₹34,206 revenue
- **Kaloo** (default): Empty, ready for new bot

## Testing: Iterations 10-19 all 100% passing

## Remaining Tasks
- (P2) Subscription Analytics (Revenue graph, churn rate, MRR dashboard)
- (P2) Resend domain verification (Email OTPs - blocked on user action)
- (P2) Production deployment sync ("Save to Github" + Coolify redeploy)
- (P3) WhatsApp integration
- (P3) Multi-language bot support
- (P3) MiniApp.jsx refactoring (1400+ lines - split into subcomponents)
