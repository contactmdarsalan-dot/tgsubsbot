# Telegram Subscription Bot - PRD

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

## Architecture
- **Backend**: FastAPI (Python) with MongoDB
- **Frontend**: React with Tailwind CSS + Shadcn UI
- **Database**: MongoDB
- **Scheduler**: APScheduler for automated tasks
- **Payments**: Razorpay integration + Manual QR verification
- **Auth**: JWT + Google OAuth (Emergent Auth)

## User Personas
1. **Super Admin (gamerxboys8958@gmail.com)**: Full control with SPECIAL DARK PANEL - users, admins, subscriptions, support
2. **Admin**: Limited powers - can view support tickets and respond
3. **Dashboard Users**: Pay for access to manage their Telegram bot
4. **Telegram Subscribers**: Pay for access to private channel

## What's Been Implemented

### Feb 4, 2026 - Session 2 (Latest)
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

### P1 (Important) - Pending
- [ ] Razorpay Gateway for Bot Subscriptions (Needs user API keys)
- [ ] Twilio OTP for phone login (Needs user credentials)

### P2 (Nice to have)
- [ ] Email notifications
- [ ] Export to CSV
- [ ] Code refactoring

## Test Credentials
- **Super Admin**: gamerxboys8958@gmail.com / admin123
- **Admin User**: admin@test.com / test123
- **Regular User**: testsuperadmin@test.com / test123
