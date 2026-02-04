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
- **Super Admin Dashboard**: Manage all SaaS subscriptions

## Architecture
- **Backend**: FastAPI (Python) with MongoDB
- **Frontend**: React with Tailwind CSS + Shadcn UI
- **Database**: MongoDB
- **Scheduler**: APScheduler for automated tasks
- **Payments**: Razorpay integration + Manual QR verification

## User Personas
1. **Super Admin (gamerxboys8958@gmail.com)**: Full control over all users and subscriptions
2. **Admin/Business Owner**: Manages their bot subscriptions, views analytics, configures bot
3. **Telegram Subscribers**: Pay for access to private channel

## Core Requirements (Static)
1. Auth system with JWT
2. Subscription plans CRUD
3. Subscriber management
4. Payment tracking (Razorpay + Manual)
5. Automated reminders and follow-ups
6. Telegram bot integration
7. SaaS subscription model for dashboard
8. Super Admin Dashboard for managing all users

## What's Been Implemented

### Feb 4, 2026 - Super Admin Dashboard
- [x] Super Admin Dashboard (`/super-admin`) - Only accessible by gamerxboys8958@gmail.com
- [x] API: GET `/api/admin/all-users` - Returns all users with subscription details
- [x] API: GET `/api/admin/stats` - Returns total_users, active_subscribers, pending_requests, total_revenue
- [x] API: GET `/api/admin/subscription-requests` - Returns all subscription requests
- [x] API: PUT `/api/admin/set-lifetime/{user_id}` - Grants lifetime access
- [x] API: PUT `/api/admin/revoke-access/{user_id}` - Revokes user access
- [x] Frontend: Stats cards, Users table, Search/Filter, Lifetime/Revoke buttons
- [x] Access control: Non-super-admin gets 403 error

### Feb 2, 2026 - SaaS & Bot Features
- [x] SaaS subscription model with pricing page
- [x] Renewal flow for expired subscriptions
- [x] Plan-specific Telegram channels
- [x] `/share` command with shareable button message
- [x] Renew button in renewal reminders
- [x] Screenshot viewing in payment verification

### Earlier - Core Features
- [x] User authentication (register/login with JWT)
- [x] Subscription Plans CRUD API
- [x] Subscribers management API
- [x] Payments API (Razorpay + Manual QR)
- [x] Settings API (bot token, channel ID, website link)
- [x] Analytics API
- [x] Telegram webhook handler
- [x] APScheduler for automated tasks

## Prioritized Backlog

### P0 (Critical) - DONE
- All core features implemented and tested
- Super Admin Dashboard complete

### P1 (Important) - Pending
- [ ] Twilio OTP for phone-based login (User requested, needs Twilio credentials)

### P2 (Nice to have)
- [ ] Multi-admin support
- [ ] Subscription tier upgrades/downgrades
- [ ] Referral system
- [ ] Promo codes/discounts
- [ ] Export subscribers to CSV
- [ ] Code refactoring (server.py modularization)

## Test Credentials
- **Super Admin**: gamerxboys8958@gmail.com / admin123
- **Regular User**: testsuperadmin@test.com / test123
- **Lifetime User**: sumitrawat77011@gmail.com

## Key Files
- `/app/backend/server.py` - All backend APIs
- `/app/frontend/src/pages/SuperAdminDashboard.jsx` - Super Admin UI
- `/app/frontend/src/components/Layout.jsx` - Navigation
- `/app/test_reports/iteration_2.json` - Latest test results
