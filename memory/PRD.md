# TgSubsBot - Telegram Subscription Bot SaaS Platform

## Original Problem Statement
Build a market-ready SaaS product for Telegram subscription management. Features include automated payment verification, live stream management, super chat, channel/group management, and a modern admin dashboard.

## Architecture
```
/app/backend/
├── server.py              # App setup, middleware (79 lines)
├── config.py              # Env vars, logging
├── database.py            # MongoDB + Redis
├── routes/
│   ├── auth.py            # Auth, Forgot Password (email), Support
│   ├── admin.py           # Dashboard, User Management
│   ├── core.py            # Plans, Payments, PDF Export, Branding, Bot Language
│   ├── features.py        # Templates, Broadcast, Live, Telegram file proxy
│   └── telegram_webhook.py # Webhook + admin approve/reject
├── services/
│   ├── auth.py, telegram.py, payment.py, chat_pool.py
│   ├── bot_activity.py, background_tasks.py, email_service.py
│   └── csv_export.py
└── models/__init__.py

/app/frontend/src/
├── components/Layout.jsx  # Dynamic branding, role-based sidebar
├── pages/ (20+ pages including Branding, BotLanguage)
├── App.js
└── index.css
```

## Implementation Log

### Mar 31, 2026 - Critical Bug Fixes
- [x] **Plan channel mapping**: Warning badge on plans without channel_id. Channel/group dropdown selector in plan editor.
- [x] **Payment screenshot thumbnails**: Inline image preview in Payments table (clickable).
- [x] **Live Stream ticket screenshots**: Actual image shown instead of text link.
- [x] **Branding super admin only**: Moved to super admin sidebar section. Backend 403 for non-super-admins.
- [x] **Functional branding**: CSS variables dynamically applied (primary color → HSL), favicon, page title, sidebar brand name/tagline, footer text all update from branding settings.
- [x] **Backend logging**: Warning logged when plan falls back to default channel.

### Mar 28, 2026 - All Features
- [x] Telegram Admin Approve/Reject buttons, User Management fix
- [x] Email integration (Resend - MOCKED), PDF Export, Branding page, Bot Language page
- [x] TG Admin Edit button
- [x] Paid Posts unlocked success tab + button states
- [x] Backend refactoring (9400→79 lines), Docker fix

## Backlog
### P0 - Deploy
- [ ] User: "Save to Github" → Coolify redeploy
- [ ] User: Set channel_id per plan in production (critical!)

### P1
- [ ] Add RESEND_API_KEY for email OTP (MOCKED)
- [ ] Razorpay improvements

### P2+
- [ ] WhatsApp, Mobile app, Custom domain

## Credentials
- Super Admin: gamerxboys8958@gmail.com / Sumit@8958
- Bot Token: 8275964628:AAH8U7ECRII7eyAySt7U2pyDQhLcnZunTnY
