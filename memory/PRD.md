# Tgsubsbot - Telegram Subscription Bot PRD

## Original Problem Statement
User requested a Telegram Subscription Bot with:
- Multiple subscription plans
- Analytics dashboard
- Auto-add to private channel on subscription purchase
- 3-4 days before expiry renewal reminder
- 1-2 extra grace days if not renewed
- Auto-remove from channel after grace period
- Auto DM website link on subscription
- Regular follow-up messages 2x per week
- Payment: Razorpay + Manual QR code
- **SaaS Model**: Dashboard itself subscription-based
- **Super Admin Dashboard**: Manage all SaaS subscriptions (SPECIAL PANEL)

## Deployment (VPS - Coolify)
- **Frontend URL**: https://tgsubsbot.com
- **Backend API URL**: https://api.tgsubsbot.com
- **Webhook**: https://api.tgsubsbot.com/api/telegram/webhook
- **Coolify Panel**: http://72.61.244.69:8000
- **Deployment**: Docker Compose via Coolify on Hostinger VPS

## Architecture
- **Backend**: FastAPI (Python) with MongoDB
- **Frontend**: React with Tailwind CSS + Shadcn UI
- **Database**: MongoDB
- **Scheduler**: APScheduler for automated tasks
- **Payments**: Razorpay integration + Manual QR verification
- **Auth**: JWT + Google OAuth (Emergent Auth) + Twilio OTP

## User Personas
1. **Super Admin (gamerxboys8958@gmail.com)**: Full control with SPECIAL DARK PANEL - users, admins, subscriptions, support
2. **Admin**: Limited powers - can view support tickets and respond
3. **Dashboard Users**: Pay for access to manage their Telegram bot
4. **Telegram Subscribers**: Pay for access to private channel

## What's Been Implemented

### Mar 23, 2026 - Session (Current)
- [x] **Branding Update** - Changed all "SubsBot" references to "Tgsubsbot"
  - Browser title updated
  - Login page header and footer updated
  - Dashboard sidebar branding updated
  - Deployment zip file recreated

### VPS Deployment (Previous Session - Completed)
- [x] Full VPS migration from Emergent preview to user's Hostinger VPS
- [x] Docker Compose setup with Coolify panel
- [x] Frontend build fixes (date-fns dependency, npm --force)
- [x] Telegram webhook configured for new domain
- [x] Production database seeded with plans and admin user

### Feb 4, 2026 - Session 2
- [x] **Super Admin SPECIAL PANEL** - Dark purple gradient theme, completely different from normal dashboard
  - User Management tab with all users, roles, plans, actions
  - Support Tickets tab with chat-style messaging
  - Quick stats: Total Users, Active Subs, Lifetime, Admins, Open Tickets, Revenue
- [x] **Chat-Style Support System** - Multiple messages, expand/collapse tickets
- [x] **Payment Reject Button** - Working with confirmation
- [x] **Google Login** - OAuth integration
- [x] **Admin Management** - Make/remove admins
- [x] **Subscription Change** - Change any user's plan

### Feb 4, 2026 - Session 1
- [x] Super Admin Dashboard basic structure
- [x] APIs for admin management

### Earlier
- [x] SaaS subscription model
- [x] Core Telegram bot features
- [x] Payment verification with screenshots
- [x] OCR for payment screenshot detection

## Key APIs
- `POST /api/auth/google/session` - Google OAuth
- `POST /api/support/tickets` - Create ticket
- `POST /api/support/tickets/{id}/message` - Add user message
- `POST /api/admin/support/tickets/{id}/reply` - Admin reply (multiple)
- `PUT /api/admin/make-admin/{id}` - Make user admin
- `PUT /api/admin/remove-admin/{id}` - Remove admin
- `PUT /api/admin/change-subscription/{id}` - Change plan
- `PUT /api/payments/{id}/reject` - Reject payment

## Prioritized Backlog

### P0 (Critical) - DONE ✅
- All core features complete
- Super Admin SPECIAL Panel complete
- Support System (chat-style) complete
- Payment Reject working
- VPS Deployment complete
- Branding update complete (Tgsubsbot)

### P1 (Important) - Pending
- [ ] Full E2E Testing on VPS deployment (subscription flow, OCR, payments)
- [ ] Add Chat Groups in production for Time-Limited Chat feature
- [ ] Razorpay Gateway for Bot Subscriptions (Needs user API keys)
- [ ] Twilio OTP for phone login (Needs user credentials)

### P2 (Nice to have)
- [ ] Email notifications (Resend integration)
- [ ] Export to CSV
- [ ] Backend code refactoring (server.py is 4000+ lines)

## Test Credentials
- **Super Admin**: gamerxboys8958@gmail.com / Sumit@8958
- **Bot Token**: 8275964628:AAH8U7ECRII7eyAySt7U2pyDQhLcnZunTnY
- **VPS IP**: 72.61.244.69

## Key Files
- `/app/docker-compose.yml` - VPS deployment configuration
- `/app/frontend/public/telegram-bot-deploy.zip` - Deployment archive
- `/app/backend/server.py` - Main backend (needs refactoring)
