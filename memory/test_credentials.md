# Test Credentials

## Super Admin
- **Email:** gamerxboys8958@gmail.com
- **Password:** Sumit@8958
- **Role:** super_admin

## Tenant Admin (Anamika)
- **Email:** anamika@test.com
- **Password:** Admin123
- **Role:** tenant_admin
- **Tenant ID:** tenant_85ee971d0285

## Bot Token (Preview/Mock)
- Uses mock Telegram bot token in preview environment

## Important URLs
- **Preview:** https://trial-management-hub-1.preview.emergentagent.com
- **Production:** https://tgsubsbot.com
- **VPS IP:** 72.61.244.69

## API Endpoints for Testing
- Login: POST /api/auth/login
- Check Admin: GET /api/auth/check-admin
- Tenants: GET /api/saas/tenants
- Risk Alerts: GET /api/saas/risk-alerts
- Impersonate: POST /api/saas/impersonate/{tenant_id}
- Impersonation Log: GET /api/saas/impersonation-log
- Webhook: POST /api/telegram/webhook
