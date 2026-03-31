# TgSubsBot - Telegram Subscription Bot SaaS

## Original Problem Statement
Transform a Telegram Subscription Bot into a scalable, market-ready SaaS product with multi-tenant architecture.

## Architecture
- Frontend: React + Framer Motion + Telegram WebApp SDK
- Backend: FastAPI + Motor (async MongoDB) + APScheduler
- Database: MongoDB with tenant isolation (tenant_id on all collections)
- AI: OpenAI GPT-5.2 Vision (Payment Screenshot Verification)

## Roles & Access
- **Super Admin**: Platform section (SaaS Management, Branding, User Mgmt, Admin Support, SaaS Subs) + all Operations. Sees cross-tenant data.
- **Tenant Admin**: Operations only (Dashboard, Plans, Subscribers, Payments, Revenue, TG Admins, Bot Activity, Paid Posts, Live, Creators, Groups & Channels, Broadcast, Coupons, Referrals, FAQs, Video Calls, Analytics, Automation, Settings, Bot Language, Support, Mini App Users). Sees only their tenant's data.
- **Bot Admin**: Telegram Mini App admin panel (TG User ID based).

## Sidebar Information Architecture
### Super Admin Sidebar:
- PLATFORM: SaaS Management, Branding, User Management, Admin Support, SaaS Subscriptions
- OPERATIONS: Dashboard, Plans, Subscribers, Payments, Revenue, TG Admins, Bot Activity, Paid Posts, Live, Creators, Groups & Channels, Broadcast, Coupons, Referrals, FAQs, Video Calls, Analytics, Automation, Settings, Bot Language, Support, Mini App Users

### Tenant Admin Sidebar:
- Dashboard, Plans, Subscribers, Payments, Revenue, TG Admins, Bot Activity, Paid Posts, Live, Creators, Groups & Channels, Broadcast, Coupons, Referrals, FAQs, Video Calls, Analytics, Automation, Settings, Bot Language, Support, Mini App Users

## All Completed Features
1-19. (Previous features - see changelog)
20. Tenant Admin System (email/password login, tenant-scoped data)
21. Dashboard Tenant Filtering (all routes filtered by tenant_id)
22. Dual Admin Types: Bot Admin (TG) + Dashboard Admin (Web)
23. Permissions System for bot admins
24. Super Admin sidebar with PLATFORM section at top (amber gold)
25. Tenant Admin sidebar with Operations only (matching production screenshot)

## Remaining Tasks
- (P2) Subscription Analytics (Revenue graph, churn rate, MRR)
- (P2) Resend domain verification (blocked on user)
- (P2) Production deployment sync
- (P3) WhatsApp integration
- (P3) Multi-language bot support
- (P3) MiniApp.jsx refactoring (1400+ lines)
