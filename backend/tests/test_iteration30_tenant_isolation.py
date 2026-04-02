"""
Iteration 30: Complete Tenant Isolation Testing
Tests ALL routes for proper tenant_id filtering across the platform.

Test Scenarios:
1. NEW TENANT (newtest_leak@example.com) - Should see 0 data for all routes
2. ORIGINAL TENANT (anamika@test.com) - Should see their tenant's data
3. SUPER ADMIN - Should see platform-wide stats
4. MINI APP USERS - Restricted to Super Admin only
5. SETTINGS - Tenant-isolated, no leaked bot_token/upi_id
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from test_credentials.md
SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"
SUPER_ADMIN_PASSWORD = "Sumit@8958"

TENANT_ADMIN_EMAIL = "anamika@test.com"
TENANT_ADMIN_PASSWORD = "Admin123"

NEW_TENANT_EMAIL = "newtest_leak@example.com"
NEW_TENANT_PASSWORD = "Test123!"


def get_auth_token(email: str, password: str) -> str:
    """Login and return JWT token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": email,
        "password": password
    })
    if response.status_code == 200:
        return response.json().get("token", "")
    return ""


class TestNewTenantIsolation:
    """Test that new tenant (newtest_leak) sees 0 data for all routes"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.token = get_auth_token(NEW_TENANT_EMAIL, NEW_TENANT_PASSWORD)
        assert self.token, f"Failed to login as {NEW_TENANT_EMAIL}"
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_creators_returns_empty(self):
        """GET /api/creators should return empty list for new tenant"""
        response = requests.get(f"{BASE_URL}/api/creators", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, f"Expected 0 creators, got {len(data)}"
        print(f"✓ /api/creators returns 0 items for new tenant")
    
    def test_telegram_admins_returns_empty(self):
        """GET /api/telegram-admins should return empty list for new tenant"""
        response = requests.get(f"{BASE_URL}/api/telegram-admins", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, f"Expected 0 TG admins, got {len(data)}"
        print(f"✓ /api/telegram-admins returns 0 items for new tenant")
    
    def test_live_sessions_returns_empty(self):
        """GET /api/live/sessions should return empty list for new tenant"""
        response = requests.get(f"{BASE_URL}/api/live/sessions", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, f"Expected 0 live sessions, got {len(data)}"
        print(f"✓ /api/live/sessions returns 0 items for new tenant")
    
    def test_paid_posts_returns_empty(self):
        """GET /api/paid-posts should return empty list for new tenant"""
        response = requests.get(f"{BASE_URL}/api/paid-posts", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, f"Expected 0 paid posts, got {len(data)}"
        print(f"✓ /api/paid-posts returns 0 items for new tenant")
    
    def test_superchats_returns_empty(self):
        """GET /api/live/superchats should return empty list for new tenant"""
        response = requests.get(f"{BASE_URL}/api/live/superchats", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, f"Expected 0 superchats, got {len(data)}"
        print(f"✓ /api/live/superchats returns 0 items for new tenant")
    
    def test_live_tickets_returns_empty(self):
        """GET /api/live/tickets should return empty list for new tenant"""
        response = requests.get(f"{BASE_URL}/api/live/tickets", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, f"Expected 0 live tickets, got {len(data)}"
        print(f"✓ /api/live/tickets returns 0 items for new tenant")
    
    def test_coupons_returns_empty(self):
        """GET /api/coupons should return empty list for new tenant"""
        response = requests.get(f"{BASE_URL}/api/coupons", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, f"Expected 0 coupons, got {len(data)}"
        print(f"✓ /api/coupons returns 0 items for new tenant")
    
    def test_faqs_returns_empty(self):
        """GET /api/faqs should return empty list for new tenant"""
        response = requests.get(f"{BASE_URL}/api/faqs", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, f"Expected 0 FAQs, got {len(data)}"
        print(f"✓ /api/faqs returns 0 items for new tenant")
    
    def test_video_calls_returns_empty(self):
        """GET /api/video-calls should return empty list for new tenant"""
        response = requests.get(f"{BASE_URL}/api/video-calls", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, f"Expected 0 video calls, got {len(data)}"
        print(f"✓ /api/video-calls returns 0 items for new tenant")
    
    def test_broadcasts_returns_empty(self):
        """GET /api/broadcasts should return empty list for new tenant"""
        response = requests.get(f"{BASE_URL}/api/broadcasts", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, f"Expected 0 broadcasts, got {len(data)}"
        print(f"✓ /api/broadcasts returns 0 items for new tenant")
    
    def test_templates_returns_empty(self):
        """GET /api/templates should return empty list for new tenant"""
        response = requests.get(f"{BASE_URL}/api/templates", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, f"Expected 0 templates, got {len(data)}"
        print(f"✓ /api/templates returns 0 items for new tenant")
    
    def test_chat_groups_returns_empty(self):
        """GET /api/chat-groups should return empty list for new tenant"""
        response = requests.get(f"{BASE_URL}/api/chat-groups", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, f"Expected 0 chat groups, got {len(data)}"
        print(f"✓ /api/chat-groups returns 0 items for new tenant")
    
    def test_channels_returns_empty(self):
        """GET /api/channels should return empty list for new tenant"""
        response = requests.get(f"{BASE_URL}/api/channels", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, f"Expected 0 channels, got {len(data)}"
        print(f"✓ /api/channels returns 0 items for new tenant")
    
    def test_bot_activity_returns_empty(self):
        """GET /api/bot-activity should return empty list for new tenant"""
        response = requests.get(f"{BASE_URL}/api/bot-activity", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, f"Expected 0 bot activity logs, got {len(data)}"
        print(f"✓ /api/bot-activity returns 0 items for new tenant")
    
    def test_blocked_users_returns_empty(self):
        """GET /api/blocked-users should return empty list for new tenant"""
        response = requests.get(f"{BASE_URL}/api/blocked-users", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, f"Expected 0 blocked users, got {len(data)}"
        print(f"✓ /api/blocked-users returns 0 items for new tenant")
    
    def test_tags_returns_empty(self):
        """GET /api/tags should return empty list for new tenant"""
        response = requests.get(f"{BASE_URL}/api/tags", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, f"Expected 0 tags, got {len(data)}"
        print(f"✓ /api/tags returns 0 items for new tenant")
    
    def test_unlock_requests_returns_empty(self):
        """GET /api/unlock-requests should return empty list for new tenant"""
        response = requests.get(f"{BASE_URL}/api/unlock-requests", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, f"Expected 0 unlock requests, got {len(data)}"
        print(f"✓ /api/unlock-requests returns 0 items for new tenant")
    
    def test_referrals_returns_empty(self):
        """GET /api/referrals should return empty list for new tenant"""
        response = requests.get(f"{BASE_URL}/api/referrals", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, f"Expected 0 referrals, got {len(data)}"
        print(f"✓ /api/referrals returns 0 items for new tenant")


class TestOriginalTenantData:
    """Test that original tenant (anamika@test.com) sees their data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.token = get_auth_token(TENANT_ADMIN_EMAIL, TENANT_ADMIN_PASSWORD)
        assert self.token, f"Failed to login as {TENANT_ADMIN_EMAIL}"
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_creators_has_data(self):
        """GET /api/creators should return at least 1 creator for original tenant"""
        response = requests.get(f"{BASE_URL}/api/creators", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1, f"Expected at least 1 creator, got {len(data)}"
        print(f"✓ /api/creators returns {len(data)} items for original tenant")
    
    def test_chat_groups_has_data(self):
        """GET /api/chat-groups should return 5 groups for original tenant"""
        response = requests.get(f"{BASE_URL}/api/chat-groups", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 5, f"Expected 5 chat groups, got {len(data)}"
        print(f"✓ /api/chat-groups returns {len(data)} items for original tenant")
    
    def test_paid_posts_has_data(self):
        """GET /api/paid-posts should return 39 posts for original tenant"""
        response = requests.get(f"{BASE_URL}/api/paid-posts", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 39, f"Expected 39 paid posts, got {len(data)}"
        print(f"✓ /api/paid-posts returns {len(data)} items for original tenant")
    
    def test_live_sessions_has_data(self):
        """GET /api/live/sessions should return 9 sessions for original tenant"""
        response = requests.get(f"{BASE_URL}/api/live/sessions", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 9, f"Expected 9 live sessions, got {len(data)}"
        print(f"✓ /api/live/sessions returns {len(data)} items for original tenant")
    
    def test_bot_activity_has_data(self):
        """GET /api/bot-activity should return >0 logs for original tenant"""
        response = requests.get(f"{BASE_URL}/api/bot-activity", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, f"Expected >0 bot activity logs, got {len(data)}"
        print(f"✓ /api/bot-activity returns {len(data)} items for original tenant")
    
    def test_telegram_admins_has_data(self):
        """GET /api/telegram-admins should return 2 admins for original tenant"""
        response = requests.get(f"{BASE_URL}/api/telegram-admins", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2, f"Expected 2 TG admins, got {len(data)}"
        print(f"✓ /api/telegram-admins returns {len(data)} items for original tenant")


class TestSuperAdminAccess:
    """Test Super Admin can access platform-wide stats"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.token = get_auth_token(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
        assert self.token, f"Failed to login as {SUPER_ADMIN_EMAIL}"
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_admin_stats_returns_platform_data(self):
        """GET /api/admin/stats should return platform-wide stats"""
        response = requests.get(f"{BASE_URL}/api/admin/stats", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        # Check platform section exists
        assert "platform" in data, "Missing 'platform' section in admin stats"
        platform = data["platform"]
        assert "total_users" in platform
        assert "total_tenants" in platform
        assert "active_tenants" in platform
        
        # Check bot_ecosystem section exists
        assert "bot_ecosystem" in data, "Missing 'bot_ecosystem' section in admin stats"
        bot = data["bot_ecosystem"]
        assert "total_bot_users" in bot
        assert "total_subscribers" in bot
        
        print(f"✓ /api/admin/stats returns platform data: {platform['total_tenants']} tenants, {bot['total_subscribers']} subscribers")
    
    def test_miniapp_users_accessible_by_super_admin(self):
        """GET /api/miniapp-users should succeed for super admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp-users", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ /api/miniapp-users accessible by super admin, returns {len(data)} users")


class TestMiniAppUsersRestriction:
    """Test Mini App Users is restricted to Super Admin only"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.new_tenant_token = get_auth_token(NEW_TENANT_EMAIL, NEW_TENANT_PASSWORD)
        self.tenant_admin_token = get_auth_token(TENANT_ADMIN_EMAIL, TENANT_ADMIN_PASSWORD)
    
    def test_miniapp_users_forbidden_for_new_tenant(self):
        """GET /api/miniapp-users should return 403 for non-super-admin"""
        headers = {"Authorization": f"Bearer {self.new_tenant_token}"}
        response = requests.get(f"{BASE_URL}/api/miniapp-users", headers=headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"✓ /api/miniapp-users returns 403 for new tenant (non-admin)")
    
    def test_miniapp_users_forbidden_for_tenant_admin(self):
        """GET /api/miniapp-users should return 403 for tenant admin"""
        headers = {"Authorization": f"Bearer {self.tenant_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/miniapp-users", headers=headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"✓ /api/miniapp-users returns 403 for tenant admin")


class TestSettingsIsolation:
    """Test Settings endpoint returns empty defaults for new tenant"""
    
    def test_settings_returns_empty_defaults_for_new_tenant(self):
        """GET /api/settings should return empty defaults (no leaked bot_token/upi_id)"""
        token = get_auth_token(NEW_TENANT_EMAIL, NEW_TENANT_PASSWORD)
        assert token, f"Failed to login as {NEW_TENANT_EMAIL}"
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/settings", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # Check that sensitive fields are empty/default
        bot_token = data.get("telegram_bot_token", "")
        upi_id = data.get("upi_id", "")
        
        # These should be empty for a new tenant
        assert not bot_token or bot_token == "", f"Leaked bot_token: {bot_token[:20]}..."
        assert not upi_id or upi_id == "", f"Leaked upi_id: {upi_id}"
        
        print(f"✓ /api/settings returns empty defaults for new tenant (no leaked data)")
    
    def test_settings_returns_data_for_original_tenant(self):
        """GET /api/settings should return tenant's own settings"""
        token = get_auth_token(TENANT_ADMIN_EMAIL, TENANT_ADMIN_PASSWORD)
        assert token, f"Failed to login as {TENANT_ADMIN_EMAIL}"
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/settings", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # Original tenant should have their settings
        assert "id" in data
        print(f"✓ /api/settings returns tenant's own settings")


class TestScheduledBroadcastsIsolation:
    """Test scheduled broadcasts are tenant-isolated"""
    
    def test_scheduled_broadcasts_empty_for_new_tenant(self):
        """GET /api/scheduled-broadcasts should return empty for new tenant"""
        token = get_auth_token(NEW_TENANT_EMAIL, NEW_TENANT_PASSWORD)
        assert token
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/scheduled-broadcasts", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, f"Expected 0 scheduled broadcasts, got {len(data)}"
        print(f"✓ /api/scheduled-broadcasts returns 0 items for new tenant")


class TestPlansIsolation:
    """Test plans are tenant-isolated"""
    
    def test_plans_empty_for_new_tenant(self):
        """GET /api/plans should return empty for new tenant"""
        token = get_auth_token(NEW_TENANT_EMAIL, NEW_TENANT_PASSWORD)
        assert token
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/plans", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, f"Expected 0 plans, got {len(data)}"
        print(f"✓ /api/plans returns 0 items for new tenant")
    
    def test_plans_has_data_for_original_tenant(self):
        """GET /api/plans should return plans for original tenant"""
        token = get_auth_token(TENANT_ADMIN_EMAIL, TENANT_ADMIN_PASSWORD)
        assert token
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/plans", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, f"Expected >0 plans, got {len(data)}"
        print(f"✓ /api/plans returns {len(data)} items for original tenant")


class TestSubscribersIsolation:
    """Test subscribers are tenant-isolated"""
    
    def test_subscribers_empty_for_new_tenant(self):
        """GET /api/subscribers should return empty for new tenant"""
        token = get_auth_token(NEW_TENANT_EMAIL, NEW_TENANT_PASSWORD)
        assert token
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/subscribers", headers=headers)
        assert response.status_code == 200
        data = response.json()
        # Response could be list or paginated object
        if isinstance(data, dict):
            subscribers = data.get("subscribers", [])
        else:
            subscribers = data
        assert len(subscribers) == 0, f"Expected 0 subscribers, got {len(subscribers)}"
        print(f"✓ /api/subscribers returns 0 items for new tenant")


class TestPaymentsIsolation:
    """Test payments are tenant-isolated"""
    
    def test_payments_empty_for_new_tenant(self):
        """GET /api/payments should return empty for new tenant"""
        token = get_auth_token(NEW_TENANT_EMAIL, NEW_TENANT_PASSWORD)
        assert token
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/payments", headers=headers)
        assert response.status_code == 200
        data = response.json()
        # Response could be list or paginated object
        if isinstance(data, dict):
            payments = data.get("payments", [])
        else:
            payments = data
        assert len(payments) == 0, f"Expected 0 payments, got {len(payments)}"
        print(f"✓ /api/payments returns 0 items for new tenant")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
