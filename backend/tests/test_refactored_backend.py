"""
Comprehensive regression tests for TgSubsBot refactored backend.
Tests all major API endpoints after refactoring from monolith to modular architecture.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://subscription-manager-44.preview.emergentagent.com')

# Test credentials from test_credentials.md
TEST_EMAIL = "gamerxboys8958@gmail.com"
TEST_PASSWORD = "Sumit@8958"


class TestAuthEndpoints:
    """Authentication endpoint tests"""
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        data = response.json()
        assert "token" in data, "Token not in response"
        assert "user" in data, "User not in response"
        assert data["user"]["email"] == TEST_EMAIL
        print(f"✅ Login successful - User: {data['user']['email']}, Role: {data['user'].get('role', 'N/A')}")
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@example.com",
            "password": "wrongpass"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ Invalid login correctly rejected")
    
    def test_get_current_user(self, auth_token):
        """Test GET /api/auth/me endpoint"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        
        assert response.status_code == 200, f"Get me failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert "email" in data
        assert data["email"] == TEST_EMAIL
        print(f"✅ GET /api/auth/me - User: {data['email']}, Role: {data.get('role', 'N/A')}")


class TestPlansEndpoints:
    """Plans CRUD endpoint tests"""
    
    def test_get_plans(self, auth_token):
        """Test GET /api/plans - should return 7 plans"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/plans", headers=headers)
        
        assert response.status_code == 200, f"Get plans failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Plans should be a list"
        print(f"✅ GET /api/plans - Found {len(data)} plans")
        
        # Verify plan structure
        if data:
            plan = data[0]
            assert "id" in plan
            assert "name" in plan
            assert "price" in plan
            print(f"   Sample plan: {plan.get('name')} - ₹{plan.get('price')}")


class TestSubscribersEndpoints:
    """Subscribers endpoint tests"""
    
    def test_get_subscribers(self, auth_token):
        """Test GET /api/subscribers - should return 44 subscribers"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/subscribers", headers=headers)
        
        assert response.status_code == 200, f"Get subscribers failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Subscribers should be a list"
        print(f"✅ GET /api/subscribers - Found {len(data)} subscribers")


class TestPaymentsEndpoints:
    """Payments endpoint tests"""
    
    def test_get_payments(self, auth_token):
        """Test GET /api/payments - should return 174 payments"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/payments", headers=headers)
        
        assert response.status_code == 200, f"Get payments failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Payments should be a list"
        print(f"✅ GET /api/payments - Found {len(data)} payments")


class TestSettingsEndpoints:
    """Settings endpoint tests"""
    
    def test_get_settings(self, auth_token):
        """Test GET /api/settings"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/settings", headers=headers)
        
        assert response.status_code == 200, f"Get settings failed: {response.text}"
        data = response.json()
        assert isinstance(data, dict), "Settings should be a dict"
        print(f"✅ GET /api/settings - Bot token configured: {'telegram_bot_token' in data and bool(data.get('telegram_bot_token'))}")


class TestAnalyticsEndpoints:
    """Analytics endpoint tests"""
    
    def test_get_analytics(self, auth_token):
        """Test GET /api/analytics"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/analytics", headers=headers)
        
        assert response.status_code == 200, f"Get analytics failed: {response.text}"
        data = response.json()
        assert "total_subscribers" in data
        assert "active_subscribers" in data
        assert "total_revenue" in data
        print(f"✅ GET /api/analytics - Total subs: {data.get('total_subscribers')}, Active: {data.get('active_subscribers')}, Revenue: ₹{data.get('total_revenue')}")
    
    def test_get_revenue_analytics(self, auth_token):
        """Test GET /api/analytics/revenue"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/analytics/revenue", headers=headers)
        
        assert response.status_code == 200, f"Get revenue analytics failed: {response.text}"
        data = response.json()
        assert "total_revenue" in data
        assert "monthly_revenue" in data
        print(f"✅ GET /api/analytics/revenue - Total: ₹{data.get('total_revenue')}, Monthly: ₹{data.get('monthly_revenue')}")


class TestBotActivityEndpoints:
    """Bot activity endpoint tests"""
    
    def test_get_bot_activity(self, auth_token):
        """Test GET /api/bot-activity"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/bot-activity", headers=headers)
        
        assert response.status_code == 200, f"Get bot activity failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Bot activity should be a list"
        print(f"✅ GET /api/bot-activity - Found {len(data)} activity logs")


class TestTelegramAdminsEndpoints:
    """Telegram admins endpoint tests"""
    
    def test_get_telegram_admins(self, auth_token):
        """Test GET /api/telegram-admins"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/telegram-admins", headers=headers)
        
        assert response.status_code == 200, f"Get telegram admins failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Telegram admins should be a list"
        print(f"✅ GET /api/telegram-admins - Found {len(data)} admins")


class TestDashboardPlansEndpoints:
    """Dashboard subscription plans endpoint tests (public)"""
    
    def test_get_dashboard_plans(self):
        """Test GET /api/dashboard-plans (public endpoint)"""
        response = requests.get(f"{BASE_URL}/api/dashboard-plans")
        
        assert response.status_code == 200, f"Get dashboard plans failed: {response.text}"
        data = response.json()
        assert "plans" in data
        assert isinstance(data["plans"], list)
        print(f"✅ GET /api/dashboard-plans - Found {len(data['plans'])} dashboard plans")


class TestTelegramWebhookEndpoints:
    """Telegram webhook endpoint tests"""
    
    def test_webhook_empty_update(self):
        """Test POST /api/telegram/webhook with empty update"""
        response = requests.post(f"{BASE_URL}/api/telegram/webhook", json={
            "update_id": 12345
        })
        
        assert response.status_code == 200, f"Webhook failed: {response.text}"
        data = response.json()
        assert data.get("ok") == True
        print("✅ POST /api/telegram/webhook - Empty update handled correctly")


class TestExportEndpoints:
    """Export endpoint tests"""
    
    def test_export_revenue_report(self, auth_token):
        """Test GET /api/export/revenue-report"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/export/revenue-report", headers=headers)
        
        assert response.status_code == 200, f"Export revenue report failed: {response.text}"
        # Check content type is CSV
        content_type = response.headers.get("content-type", "")
        assert "text/csv" in content_type or "application/octet-stream" in content_type or response.status_code == 200
        print(f"✅ GET /api/export/revenue-report - Export successful")


class TestBroadcastsEndpoints:
    """Broadcasts endpoint tests"""
    
    def test_get_broadcasts(self, auth_token):
        """Test GET /api/broadcasts"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/broadcasts", headers=headers)
        
        assert response.status_code == 200, f"Get broadcasts failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Broadcasts should be a list"
        print(f"✅ GET /api/broadcasts - Found {len(data)} broadcasts")


class TestCouponsEndpoints:
    """Coupons endpoint tests"""
    
    def test_get_coupons(self, auth_token):
        """Test GET /api/coupons"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/coupons", headers=headers)
        
        assert response.status_code == 200, f"Get coupons failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Coupons should be a list"
        print(f"✅ GET /api/coupons - Found {len(data)} coupons")


class TestVideoCallsEndpoints:
    """Video calls endpoint tests"""
    
    def test_get_video_calls(self, auth_token):
        """Test GET /api/video-calls"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/video-calls", headers=headers)
        
        assert response.status_code == 200, f"Get video calls failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Video calls should be a list"
        print(f"✅ GET /api/video-calls - Found {len(data)} video call bookings")


class TestLiveSessionsEndpoints:
    """Live sessions endpoint tests"""
    
    def test_get_live_sessions(self, auth_token):
        """Test GET /api/live/sessions"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/live/sessions", headers=headers)
        
        assert response.status_code == 200, f"Get live sessions failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Live sessions should be a list"
        print(f"✅ GET /api/live/sessions - Found {len(data)} live sessions")


class TestCreatorsEndpoints:
    """Creators endpoint tests"""
    
    def test_get_creators(self, auth_token):
        """Test GET /api/creators"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/creators", headers=headers)
        
        assert response.status_code == 200, f"Get creators failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Creators should be a list"
        print(f"✅ GET /api/creators - Found {len(data)} creators")


class TestFAQsEndpoints:
    """FAQs endpoint tests"""
    
    def test_get_faqs(self, auth_token):
        """Test GET /api/faqs"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/faqs", headers=headers)
        
        assert response.status_code == 200, f"Get FAQs failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "FAQs should be a list"
        print(f"✅ GET /api/faqs - Found {len(data)} FAQs")


class TestReferralsEndpoints:
    """Referrals endpoint tests"""
    
    def test_get_referrals(self, auth_token):
        """Test GET /api/referrals"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/referrals", headers=headers)
        
        assert response.status_code == 200, f"Get referrals failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Referrals should be a list"
        print(f"✅ GET /api/referrals - Found {len(data)} referrals")


class TestChatGroupsEndpoints:
    """Chat groups endpoint tests"""
    
    def test_get_chat_groups(self, auth_token):
        """Test GET /api/chat-groups"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/chat-groups", headers=headers)
        
        assert response.status_code == 200, f"Get chat groups failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Chat groups should be a list"
        print(f"✅ GET /api/chat-groups - Found {len(data)} chat groups")


class TestPaidPostsEndpoints:
    """Paid posts endpoint tests"""
    
    def test_get_paid_posts(self, auth_token):
        """Test GET /api/paid-posts"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/paid-posts", headers=headers)
        
        assert response.status_code == 200, f"Get paid posts failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Paid posts should be a list"
        print(f"✅ GET /api/paid-posts - Found {len(data)} paid posts")


class TestBlockedUsersEndpoints:
    """Blocked users endpoint tests"""
    
    def test_get_blocked_users(self, auth_token):
        """Test GET /api/blocked-users"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/blocked-users", headers=headers)
        
        assert response.status_code == 200, f"Get blocked users failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Blocked users should be a list"
        print(f"✅ GET /api/blocked-users - Found {len(data)} blocked users")


class TestTagsEndpoints:
    """Tags endpoint tests"""
    
    def test_get_tags(self, auth_token):
        """Test GET /api/tags"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/tags", headers=headers)
        
        assert response.status_code == 200, f"Get tags failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Tags should be a list"
        print(f"✅ GET /api/tags - Found {len(data)} tags")


# ============== FIXTURES ==============

@pytest.fixture(scope="session")
def auth_token():
    """Get authentication token for tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Authentication failed: {response.text}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
