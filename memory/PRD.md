# TgSubsBot - Telegram Subscription Bot SaaS Platform

## Original Problem Statement
Build a market-ready SaaS product for Telegram subscription management. Features include automated payment verification, live stream management, super chat, channel/group management, and a modern admin dashboard.

## User Personas
- **Bot Admin (Primary)**: Manages subscription plans, verifies payments, monitors analytics
- **Telegram Subscribers**: End users who purchase plans via the bot
- **Creators**: Manage live streams, receive super chats

## Core Requirements
1. Telegram Bot with subscription plans, payment QR, auto-verification
2. Admin Dashboard with subscriber management, analytics, broadcasts
3. Live Stream management with super chat
4. Video call booking system
5. Multi-tenant SaaS architecture (P0 - In Progress)
6. Payment gateway integration (Razorpay)

## Architecture
```
/app/backend/
├── config.py          # Env vars, logging, clients
├── database.py        # MongoDB + Redis connections
├── models/__init__.py # All Pydantic models
├── routes/            # (Planned) Modular route files
├── services/          # (Planned) Service layer
├── utils/             # (Planned) Helper utilities
└── server.py          # Main app (~8800 lines, being refactored)

/app/frontend/
├── src/
│   ├── components/ui/ # Shadcn + SeraUI animated components
│   ├── pages/         # Dashboard pages (Romance theme)
│   ├── App.js         # Routing (/ → Landing, /dashboard → Admin)
│   └── index.css      # Romance theme CSS variables
```

## Tech Stack
- Frontend: React, Tailwind CSS, Shadcn/UI, Framer Motion
- Backend: FastAPI, MongoDB (Motor async), Redis
- Bot: Telegram Bot API (Webhooks)
- AI: GPT-4o Vision (payment verification) via Emergent LLM Key
- Hosting: Coolify (production), Emergent Preview (development)

---

## Implementation Log

### Mar 27, 2026 - Subscriber Details Enhancement
- [x] Added Telegram ID, Channel ID, Group Name columns to Subscribers table
- [x] Backend GET /api/subscribers enriched with plan and group data

### Mar 28, 2026 - SaaS Infrastructure (Batch 3)
- [x] **Bot /admin command** — Admin panel in Telegram with quick stats, /stats, /pending, /broadcast, /users commands
- [x] **Admin callback buttons** — View Stats, Pending Payments, New Broadcast inline buttons
- [x] **/broadcast command** — Send message to all bot users directly from Telegram
- [x] **/users command** — View recent bot users
- [x] **Bot user tracking** — Auto-upsert user data on every webhook message
- [x] **Dashboard Setup Checklist** — Onboarding widget shows completion status (Bot Token, Channel ID, QR, Plans, Welcome Message)
- [x] **Bot Activity improved** — Empty state with deploy instructions + Refresh button

### Mar 28, 2026 - SaaS Infrastructure (Batch 2)
- [x] **Bot Activity Logs** — Real-time dashboard with 24h stats, search, filter by event type, Export CSV, Auto-Refresh (5s)
  - Activity logged for commands, button clicks, messages, payment screenshots
  - Stats: events 24h, active users 24h, commands, payments
- [x] **API Rate Limiting** — slowapi integrated: Login 10/min, Register 5/min, Webhook 300/min
- [x] **Revenue Export CSV** — Download full revenue report from Revenue Dashboard
- [x] **Enhanced Export API** — `/api/export/revenue-report` with CSV data + summary

### Mar 28, 2026 - Telegram Admin Management
- [x] **Telegram Admins page** — Full CRUD for managing bot admins from dashboard
  - Add admin with Telegram User ID, Username, Role (Admin/Moderator), granular permissions
  - Toggle active/inactive, delete with Telegram notification
  - `is_admin_or_creator` updated to check `telegram_admins` collection
  - Stats cards: Total, Active, Inactive
  - Sidebar link "TG Admins" added

### Mar 28, 2026 - Revenue Dashboard & Bug Fixes
- [x] **Revenue Analytics Dashboard** — Full page with Total Revenue, Monthly, Today, ARPU, LTV, Churn Rate
  - Area chart with Daily/Weekly/Monthly tabs
  - Plan Performance breakdown with animated bars
  - Conversion Funnel (Bot Users → Payment Started → Verified → Active)
  - Bottom stats grid (Total Payments, Active, Grace, Expired)
- [x] **Group ID Auto-Fix** — Backend now auto-prepends `-` to Group IDs (Telegram IDs are negative)
- [x] Added Revenue link in sidebar navigation

### Mar 28, 2026 - Major Feature Batch
- [x] Fixed bot payment flow - users now always get channel invite (was blocked by empty plan channel_id + use_default=False)
- [x] Added admin Telegram notification on new payments (notify_admin_new_payment)
- [x] Added bulk-add-to-channel endpoint for existing subscribers
- [x] Added 5-sec interval countdown timer on plan purchase (60s offer + 60s last chance + expired)
- [x] Added Promote Plan to Group feature (admin can share specific plan to selected Telegram group)
- [x] Added /start buy_{plan_id} deep link support for promote button
- [x] Welcome message sent to new subscribers after payment
- [x] Group auto-assignment in create_subscriber_task

### Mar 28, 2026 - Architecture Refactoring (Phase 1)
- [x] Created config.py (env vars, logging, client initialization)
- [x] Created database.py (MongoDB + Redis connections)
- [x] Created models/__init__.py (all Pydantic models extracted)
- [x] Created modular directory structure (routes/, services/, utils/)
- [x] Updated server.py to import from modules

---

## Backlog (Prioritized)

### P0 - SaaS Foundation
- [ ] Backend refactoring Phase 2: Extract routes from server.py into routes/
- [ ] Backend refactoring Phase 3: Extract services (telegram, payment, notification)
- [ ] Multi-tenant system (each customer gets own bot/dashboard)
- [ ] SaaS billing (Razorpay/Stripe for dashboard access)
- [ ] Onboarding wizard for new users

### P1 - Important Features
- [ ] Advanced analytics dashboard (revenue graphs, conversion funnel, churn rate)
- [ ] Razorpay/Stripe direct payment in bot
- [ ] Email notifications (SendGrid/Resend)
- [ ] API rate limiting & security hardening
- [ ] Mobile responsive dashboard improvements

### P2 - Nice to Have
- [ ] White-label branding (custom logo, colors, domain)
- [ ] Multi-language bot (Hindi/English)
- [ ] Affiliate/Referral system in bot
- [ ] Webhook logs & debugging panel
- [ ] Zapier/Make integration

### P3 - Future
- [ ] WhatsApp integration
- [ ] Mobile app (React Native)
- [ ] Custom domain per customer

## Credentials
- Super Admin: gamerxboys8958@gmail.com / Sumit@8958
- Bot Token: 8275964628:AAH8U7ECRII7eyAySt7U2pyDQhLcnZunTnY
- Production webhook: https://api.tgsubsbot.com/api/telegram/webhook
- Preview webhook: https://live-announce-hub.preview.emergentagent.com/api/telegram/webhook
