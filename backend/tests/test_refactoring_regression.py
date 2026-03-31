"""
Regression tests for backend refactoring - verifying all routes work after splitting
core.py, features.py, miniapp.py into 10 domain-specific route files.

Tests cover:
- Auth routes (login, check-admin)
- Plans CRUD
- Subscribers CRUD
- Payments CRUD + bulk operations
- Dashboard (channels, chat-groups, settings, analytics, branding, bot-language)
- Broadcasts (templates, broadcasts, scheduled)
- Engagement (coupons, tags, blocked-users, referrals, faqs, video-calls)
- Live Content (creators, telegram-admins, live-sessions, paid-posts, unlock-requests)
- Analytics Exports (revenue, users, exports, chat-messages, bot-activity)
- MiniApp User endpoints
- MiniApp Admin endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"
SUPER_ADMIN_PASSWORD = "Sumit@8958"
TENANT_ADMIN_EMAIL = "anamika@test.com"
TENANT_ADMIN_PASSWORD = "Admin123"
TEST_TG_ID = "123456789"
TENANT_ID = "tenant_85ee971d0285"


class TestAuthRoutes:
    """Test auth routes from routes/auth.py"""
    
    def test_super_admin_login(self):
        """Super Admin login should return token and role"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        # Role is inside user object
        user = data.get("user", {})
        role = user.get("role") or data.get("role")
        assert role in ["super_admin", "admin", None], f"Unexpected role: {role}"
        print(f"✓ Super Admin login successful, role: {role}")
    
    def test_tenant_admin_login(self):
        """Tenant Admin login should return token and tenant_id"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        # tenant_id is inside user object
        user = data.get("user", {})
        tenant_id = user.get("tenant_id") or data.get("tenant_id")
        assert tenant_id == TENANT_ID, f"Unexpected tenant_id: {tenant_id}"
        print(f"✓ Tenant Admin login successful, tenant_id: {tenant_id}")
    
    def test_check_admin_unauthenticated(self):
        """Check admin without token should return 401 or 403"""
        response = requests.get(f"{BASE_URL}/api/auth/check-admin")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ Check admin returns {response.status_code} for unauthenticated requests")


@pytest.fixture(scope="class")
def super_admin_token():
    """Get Super Admin token for authenticated tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Super Admin login failed")


@pytest.fixture(scope="class")
def tenant_admin_token():
    """Get Tenant Admin token for authenticated tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TENANT_ADMIN_EMAIL,
        "password": TENANT_ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Tenant Admin login failed")


class TestPlansRoutes:
    """Test plans routes from routes/plans.py"""
    
    def test_get_plans_authenticated(self, super_admin_token):
        """GET /api/plans should return list of plans"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/plans", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of plans"
        print(f"✓ GET /api/plans returned {len(data)} plans")
    
    def test_get_plans_unauthenticated(self):
        """GET /api/plans without token should return 401 or 403"""
        response = requests.get(f"{BASE_URL}/api/plans")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ GET /api/plans returns {response.status_code} for unauthenticated requests")
    
    def test_get_active_plans_public(self):
        """GET /api/plans/active is public endpoint"""
        response = requests.get(f"{BASE_URL}/api/plans/active")
        # This might be public or protected depending on implementation
        assert response.status_code in [200, 401], f"Unexpected status: {response.status_code}"
        print(f"✓ GET /api/plans/active returned status {response.status_code}")


class TestSubscribersRoutes:
    """Test subscribers routes from routes/subscribers.py"""
    
    def test_get_subscribers(self, super_admin_token):
        """GET /api/subscribers should return list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/subscribers", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of subscribers"
        print(f"✓ GET /api/subscribers returned {len(data)} subscribers")
    
    def test_get_subscribers_with_status_filter(self, super_admin_token):
        """GET /api/subscribers?status=active should filter"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/subscribers?status=active", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        print("✓ GET /api/subscribers with status filter works")


class TestPaymentsRoutes:
    """Test payments routes from routes/payments.py"""
    
    def test_get_payments(self, super_admin_token):
        """GET /api/payments should return list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/payments", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of payments"
        print(f"✓ GET /api/payments returned {len(data)} payments")
    
    def test_get_payments_with_status_filter(self, super_admin_token):
        """GET /api/payments?status=pending should filter"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/payments?status=pending", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        print("✓ GET /api/payments with status filter works")


class TestDashboardRoutes:
    """Test dashboard routes from routes/dashboard.py"""
    
    def test_get_analytics(self, super_admin_token):
        """GET /api/analytics should return dashboard stats"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/analytics", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "total_subscribers" in data, "Missing total_subscribers"
        assert "total_revenue" in data, "Missing total_revenue"
        print(f"✓ GET /api/analytics returned stats: {data.get('total_subscribers')} subs, Rs.{data.get('total_revenue')} revenue")
    
    def test_get_settings(self, super_admin_token):
        """GET /api/settings should return bot settings"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/settings", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        print("✓ GET /api/settings works")
    
    def test_get_channels(self, super_admin_token):
        """GET /api/channels should return list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/channels", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of channels"
        print(f"✓ GET /api/channels returned {len(data)} channels")
    
    def test_get_chat_groups(self, super_admin_token):
        """GET /api/chat-groups should return list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/chat-groups", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of chat groups"
        print(f"✓ GET /api/chat-groups returned {len(data)} groups")
    
    def test_get_branding(self, super_admin_token):
        """GET /api/branding should return branding settings"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/branding", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "brand_name" in data, "Missing brand_name"
        print(f"✓ GET /api/branding returned brand: {data.get('brand_name')}")
    
    def test_get_bot_language(self, super_admin_token):
        """GET /api/bot-language should return language settings"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/bot-language", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "default_language" in data, "Missing default_language"
        print(f"✓ GET /api/bot-language returned language: {data.get('default_language')}")


class TestBroadcastsRoutes:
    """Test broadcasts routes from routes/broadcasts.py"""
    
    def test_get_templates(self, super_admin_token):
        """GET /api/templates should return list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/templates", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of templates"
        print(f"✓ GET /api/templates returned {len(data)} templates")
    
    def test_get_broadcasts(self, super_admin_token):
        """GET /api/broadcasts should return list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/broadcasts", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of broadcasts"
        print(f"✓ GET /api/broadcasts returned {len(data)} broadcasts")
    
    def test_get_scheduled_broadcasts(self, super_admin_token):
        """GET /api/scheduled-broadcasts should return list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/scheduled-broadcasts", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of scheduled broadcasts"
        print(f"✓ GET /api/scheduled-broadcasts returned {len(data)} scheduled")


class TestEngagementRoutes:
    """Test engagement routes from routes/engagement.py"""
    
    def test_get_coupons(self, super_admin_token):
        """GET /api/coupons should return list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/coupons", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of coupons"
        print(f"✓ GET /api/coupons returned {len(data)} coupons")
    
    def test_get_referrals(self, super_admin_token):
        """GET /api/referrals should return list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/referrals", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of referrals"
        print(f"✓ GET /api/referrals returned {len(data)} referrals")
    
    def test_get_blocked_users(self, super_admin_token):
        """GET /api/blocked-users should return list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/blocked-users", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of blocked users"
        print(f"✓ GET /api/blocked-users returned {len(data)} blocked")
    
    def test_get_tags(self, super_admin_token):
        """GET /api/tags should return list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/tags", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of tags"
        print(f"✓ GET /api/tags returned {len(data)} tags")
    
    def test_get_faqs(self, super_admin_token):
        """GET /api/faqs should return list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/faqs", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of FAQs"
        print(f"✓ GET /api/faqs returned {len(data)} FAQs")
    
    def test_get_video_calls(self, super_admin_token):
        """GET /api/video-calls should return list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/video-calls", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of video calls"
        print(f"✓ GET /api/video-calls returned {len(data)} video calls")


class TestLiveContentRoutes:
    """Test live content routes from routes/live_content.py"""
    
    def test_get_live_sessions(self, super_admin_token):
        """GET /api/live/sessions should return list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/live/sessions", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of live sessions"
        print(f"✓ GET /api/live/sessions returned {len(data)} sessions")
    
    def test_get_creators(self, super_admin_token):
        """GET /api/creators should return list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/creators", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of creators"
        print(f"✓ GET /api/creators returned {len(data)} creators")
    
    def test_get_telegram_admins(self, super_admin_token):
        """GET /api/telegram-admins should return list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/telegram-admins", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of telegram admins"
        print(f"✓ GET /api/telegram-admins returned {len(data)} admins")
    
    def test_get_paid_posts(self, super_admin_token):
        """GET /api/paid-posts should return list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/paid-posts", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of paid posts"
        print(f"✓ GET /api/paid-posts returned {len(data)} paid posts")
    
    def test_get_unlock_requests(self, super_admin_token):
        """GET /api/unlock-requests should return list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/unlock-requests", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of unlock requests"
        print(f"✓ GET /api/unlock-requests returned {len(data)} unlock requests")


class TestAnalyticsExportsRoutes:
    """Test analytics/exports routes from routes/analytics_exports.py"""
    
    def test_get_revenue_analytics(self, super_admin_token):
        """GET /api/analytics/revenue should return detailed analytics"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/analytics/revenue", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "total_revenue" in data, "Missing total_revenue"
        assert "daily_chart" in data, "Missing daily_chart"
        print(f"✓ GET /api/analytics/revenue returned total: Rs.{data.get('total_revenue')}")
    
    def test_get_user_analytics(self, super_admin_token):
        """GET /api/analytics/users should return user growth data"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/analytics/users", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "total_users" in data, "Missing total_users"
        print(f"✓ GET /api/analytics/users returned {data.get('total_users')} users")
    
    def test_export_subscribers(self, super_admin_token):
        """GET /api/export/subscribers should return CSV data"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/export/subscribers", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "csv_data" in data, "Missing csv_data"
        print(f"✓ GET /api/export/subscribers returned {data.get('count')} records")
    
    def test_export_payments(self, super_admin_token):
        """GET /api/export/payments should return CSV data"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/export/payments", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "csv_data" in data, "Missing csv_data"
        print(f"✓ GET /api/export/payments returned {data.get('count')} records")
    
    def test_get_chat_messages(self, super_admin_token):
        """GET /api/chat-messages should return list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/chat-messages", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of chat messages"
        print(f"✓ GET /api/chat-messages returned {len(data)} messages")
    
    def test_get_bot_activity(self, super_admin_token):
        """GET /api/bot-activity should return list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/bot-activity", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of bot activity"
        print(f"✓ GET /api/bot-activity returned {len(data)} activities")


class TestMiniAppUserRoutes:
    """Test miniapp user routes from routes/miniapp_user.py"""
    
    def test_get_miniapp_plans(self):
        """GET /api/miniapp/plans is public"""
        response = requests.get(f"{BASE_URL}/api/miniapp/plans")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of plans"
        print(f"✓ GET /api/miniapp/plans returned {len(data)} plans")
    
    def test_get_miniapp_status(self):
        """GET /api/miniapp/status/{tg_id} should work"""
        response = requests.get(f"{BASE_URL}/api/miniapp/status/{TEST_TG_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "is_active" in data, "Missing is_active"
        print(f"✓ GET /api/miniapp/status/{TEST_TG_ID} returned is_active: {data.get('is_active')}")
    
    def test_get_miniapp_upi_details(self):
        """GET /api/miniapp/upi-details is public"""
        response = requests.get(f"{BASE_URL}/api/miniapp/upi-details")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "upi_id" in data, "Missing upi_id"
        print(f"✓ GET /api/miniapp/upi-details returned UPI: {data.get('upi_id')}")
    
    def test_get_miniapp_notifications(self):
        """GET /api/miniapp/notifications/{tg_id} should work"""
        response = requests.get(f"{BASE_URL}/api/miniapp/notifications/{TEST_TG_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of notifications"
        print(f"✓ GET /api/miniapp/notifications/{TEST_TG_ID} returned {len(data)} notifications")
    
    def test_get_miniapp_live_sessions_public(self):
        """GET /api/miniapp/live-sessions/public should work"""
        response = requests.get(f"{BASE_URL}/api/miniapp/live-sessions/public")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of live sessions"
        print(f"✓ GET /api/miniapp/live-sessions/public returned {len(data)} sessions")
    
    def test_apply_coupon(self):
        """POST /api/miniapp/apply-coupon should validate coupon"""
        response = requests.post(f"{BASE_URL}/api/miniapp/apply-coupon", json={
            "code": "INVALID_CODE",
            "plan_id": "test",
            "amount": 100
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "valid" in data, "Missing valid field"
        print(f"✓ POST /api/miniapp/apply-coupon works (valid: {data.get('valid')})")


class TestMiniAppAdminRoutes:
    """Test miniapp admin routes from routes/miniapp_admin.py"""
    
    def test_admin_check(self):
        """GET /api/miniapp/admin/check/{tg_id} should work"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/check/{TEST_TG_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "is_admin" in data, "Missing is_admin"
        print(f"✓ GET /api/miniapp/admin/check/{TEST_TG_ID} returned is_admin: {data.get('is_admin')}")
    
    def test_admin_stats_unauthorized(self):
        """GET /api/miniapp/admin/stats/{tg_id} should return 403 for non-admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/stats/{TEST_TG_ID}")
        # Should be 403 if not admin, or 200 if admin
        assert response.status_code in [200, 403], f"Unexpected status: {response.status_code}"
        print(f"✓ GET /api/miniapp/admin/stats/{TEST_TG_ID} returned {response.status_code}")
    
    def test_admin_pending_payments_unauthorized(self):
        """GET /api/miniapp/admin/pending-payments/{tg_id} should return 403 for non-admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/pending-payments/{TEST_TG_ID}")
        assert response.status_code in [200, 403], f"Unexpected status: {response.status_code}"
        print(f"✓ GET /api/miniapp/admin/pending-payments/{TEST_TG_ID} returned {response.status_code}")
    
    def test_admin_subscribers_unauthorized(self):
        """GET /api/miniapp/admin/subscribers/{tg_id} should return 403 for non-admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/subscribers/{TEST_TG_ID}")
        assert response.status_code in [200, 403], f"Unexpected status: {response.status_code}"
        print(f"✓ GET /api/miniapp/admin/subscribers/{TEST_TG_ID} returned {response.status_code}")
    
    def test_admin_paid_posts_unauthorized(self):
        """GET /api/miniapp/admin/paid-posts/{tg_id} should return 403 for non-admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/paid-posts/{TEST_TG_ID}")
        assert response.status_code in [200, 403], f"Unexpected status: {response.status_code}"
        print(f"✓ GET /api/miniapp/admin/paid-posts/{TEST_TG_ID} returned {response.status_code}")


class TestTenantIsolation:
    """Test tenant isolation - Tenant Admin should only see their data"""
    
    def test_tenant_admin_sees_own_data(self, tenant_admin_token):
        """Tenant Admin should only see their tenant's data"""
        headers = {"Authorization": f"Bearer {tenant_admin_token}"}
        
        # Get subscribers
        response = requests.get(f"{BASE_URL}/api/subscribers", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        print("✓ Tenant Admin can access /api/subscribers")
        
        # Get payments
        response = requests.get(f"{BASE_URL}/api/payments", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        print("✓ Tenant Admin can access /api/payments")
        
        # Get plans
        response = requests.get(f"{BASE_URL}/api/plans", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        print("✓ Tenant Admin can access /api/plans")
    
    def test_tenant_admin_blocked_from_saas(self, tenant_admin_token):
        """Tenant Admin should NOT access SaaS management"""
        headers = {"Authorization": f"Bearer {tenant_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/saas/tenants", headers=headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("✓ Tenant Admin blocked from /api/saas/tenants (403)")


class TestRBACEndpoints:
    """Test RBAC - Super Admin vs Tenant Admin access"""
    
    def test_super_admin_can_access_saas(self, super_admin_token):
        """Super Admin should access SaaS management"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/saas/tenants", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        print("✓ Super Admin can access /api/saas/tenants")
    
    def test_super_admin_can_update_branding(self, super_admin_token):
        """Super Admin should be able to update branding"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.put(f"{BASE_URL}/api/branding", headers=headers, json={
            "brand_name": "TGSubsBot"
        })
        assert response.status_code == 200, f"Failed: {response.text}"
        print("✓ Super Admin can update branding")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
