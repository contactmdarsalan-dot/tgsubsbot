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
5. Multi-tenant SaaS architecture
6. Payment gateway integration (Razorpay)

## Architecture (Refactored - Mar 28, 2026)
```
/app/backend/
├── server.py              # App setup, middleware, router inclusion (79 lines)
├── config.py              # Env vars, logging, clients
├── database.py            # MongoDB + Redis connections
├── rate_limiter.py        # SlowAPI rate limiter instance
├── models/
│   └── __init__.py        # All Pydantic models (340 lines)
├── services/
│   ├── auth.py            # Password hashing, JWT, user verification
│   ├── telegram.py        # Telegram API helpers (messaging, channels)
│   ├── payment.py         # OCR detection, AI analysis, image blur
│   ├── chat_pool.py       # Chat group pool management
│   ├── bot_activity.py    # Bot activity logging
│   ├── background_tasks.py # Scheduled background jobs
│   ├── csv_export.py      # CSV generation utilities
│   └── email_service.py   # Email service
├── routes/
│   ├── auth.py            # Auth, OTP, Support tickets
│   ├── admin.py           # Dashboard subscription, Super admin
│   ├── core.py            # Plans, Subscribers, Payments, Settings
│   ├── features.py        # Templates, Broadcast, Coupons, Live, etc.
│   └── telegram_webhook.py # Main webhook handler
├── tests/
│   ├── test_refactored_backend.py
│   └── ...
├── Dockerfile
└── requirements.txt

/app/frontend/
├── src/
│   ├── components/ui/     # Shadcn + SeraUI animated components
│   ├── pages/             # Dashboard pages (Romance theme)
│   │   ├── RevenueDashboard.jsx
│   │   ├── TelegramAdmins.jsx
│   │   ├── BotActivityLogs.jsx
│   │   ├── Subscribers.jsx
│   │   └── Dashboard.jsx
│   ├── App.js             # Routing
│   └── index.css          # Romance theme CSS variables
```

## Tech Stack
- Frontend: React, Tailwind CSS, Shadcn/UI, Framer Motion
- Backend: FastAPI, MongoDB (Motor async), Redis
- Bot: Telegram Bot API (Webhooks)
- AI: GPT-4o Vision (payment verification) via Emergent LLM Key
- Rate Limiting: SlowAPI
- Hosting: Coolify (production), Emergent Preview (development)

---

## Implementation Log

### Mar 28, 2026 - Backend Refactoring Phase 2 (COMPLETE)
- [x] **Monolith decomposition**: server.py reduced from 9408 lines to 79 lines
- [x] **Service layer**: Extracted auth, telegram, payment, chat_pool, bot_activity, background_tasks
- [x] **Route modules**: Split into auth, admin, core, features, telegram_webhook
- [x] **Shared rate limiter**: Created rate_limiter.py for cross-module access
- [x] **Docker deployment fix**: Removed emergentintegrations from requirements.txt (installed via Dockerfile)
- [x] **slowapi preserved**: Confirmed slowapi==0.1.9 in requirements.txt
- [x] **Full regression test**: 25/25 API tests passed, frontend verified working

### Mar 28, 2026 - SaaS Infrastructure (Previous)
- [x] Revenue Analytics Dashboard with ARPU, LTV, Churn
- [x] Bot Activity Logs with CSV Export
- [x] Telegram Admin Management
- [x] API Rate Limiting (slowapi)
- [x] Bot commands: /admin, /stats, /pending, /broadcast, /users
- [x] 5-second countdown urgency timer on plan purchase
- [x] Phase 1 refactoring: config.py, database.py, models/

---

## Backlog (Prioritized)

### P0 - Deployment
- [ ] Verify Coolify deployment (user needs to "Save to Github" and redeploy)

### P1 - Important Features
- [ ] Razorpay/Stripe direct payment in bot
- [ ] Email notifications (SendGrid/Resend)
- [ ] Mobile responsive dashboard improvements

### P2 - Nice to Have
- [ ] White-label branding (custom logo, colors, domain)
- [ ] Multi-language bot (Hindi/English)
- [ ] Revenue Dashboard PDF export
- [ ] Affiliate/Referral system enhancements

### P3 - Future
- [ ] WhatsApp integration
- [ ] Mobile app (React Native)
- [ ] Custom domain per customer

## Credentials
- Super Admin: gamerxboys8958@gmail.com / Sumit@8958
- Bot Token: 8275964628:AAH8U7ECRII7eyAySt7U2pyDQhLcnZunTnY
- Production webhook: https://api.tgsubsbot.com/api/telegram/webhook
- Preview webhook: https://subscription-manager-44.preview.emergentagent.com/api/telegram/webhook
