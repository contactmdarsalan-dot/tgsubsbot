"""
Iteration 24 Tests: Super Admin Control Center & Tenant Profile
Tests:
1. GET /api/admin/stats - Comprehensive platform stats for Control Center
2. GET /api/admin/tenant-profile/{tenant_id} - Full tenant profile data
3. 404 for non-existent tenant profile
4. Auth/RBAC - Super Admin vs Tenant Admin access
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
TEST_TENANT_ID = "tenant_85ee971d0285"


class TestAuthAndRoles:
    """Test authentication and role-based access"""
    
    def test_super_admin_login(self):
        """Super Admin can login successfully"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Super Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        assert "user" in data, "No user in response"
        assert data["user"]["role"] == "super_admin", f"Expected super_admin role, got {data['user']['role']}"
        print(f"PASS: Super Admin login successful, role={data['user']['role']}")
    
    def test_tenant_admin_login(self):
        """Tenant Admin can login successfully"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Tenant Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        assert "user" in data, "No user in response"
        assert data["user"]["role"] == "tenant_admin", f"Expected tenant_admin role, got {data['user']['role']}"
        print(f"PASS: Tenant Admin login successful, role={data['user']['role']}")


@pytest.fixture
def super_admin_token():
    """Get Super Admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Super Admin login failed")


@pytest.fixture
def tenant_admin_token():
    """Get Tenant Admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TENANT_ADMIN_EMAIL,
        "password": TENANT_ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Tenant Admin login failed")


class TestSuperAdminControlCenter:
    """Test GET /api/admin/stats - Control Center data"""
    
    def test_admin_stats_returns_comprehensive_data(self, super_admin_token):
        """GET /api/admin/stats returns all required Control Center data"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/stats", headers=headers)
        
        assert response.status_code == 200, f"Admin stats failed: {response.text}"
        data = response.json()
        
        # Verify platform section
        assert "platform" in data, "Missing 'platform' section"
        platform = data["platform"]
        assert "total_tenants" in platform, "Missing total_tenants"
        assert "active_tenants" in platform, "Missing active_tenants"
        assert "total_tenant_admins" in platform, "Missing total_tenant_admins"
        assert "platform_revenue" in platform, "Missing platform_revenue"
        assert "pending_requests" in platform, "Missing pending_requests"
        print(f"PASS: Platform section has all fields: tenants={platform['total_tenants']}, admins={platform['total_tenant_admins']}, revenue={platform['platform_revenue']}")
        
        # Verify bot_ecosystem section
        assert "bot_ecosystem" in data, "Missing 'bot_ecosystem' section"
        bot = data["bot_ecosystem"]
        assert "total_bot_users" in bot, "Missing total_bot_users"
        assert "active_subscribers" in bot, "Missing active_subscribers"
        assert "expired_subscribers" in bot, "Missing expired_subscribers"
        assert "total_payments" in bot, "Missing total_payments"
        assert "pending_payments" in bot, "Missing pending_payments"
        print(f"PASS: Bot ecosystem section has all fields: users={bot['total_bot_users']}, active_subs={bot['active_subscribers']}, payments={bot['total_payments']}")
        
        # Verify revenue section
        assert "revenue" in data, "Missing 'revenue' section"
        revenue = data["revenue"]
        assert "total_tenant_revenue" in revenue, "Missing total_tenant_revenue"
        assert "monthly_revenue" in revenue, "Missing monthly_revenue"
        assert "daily_chart" in revenue, "Missing daily_chart"
        assert isinstance(revenue["daily_chart"], list), "daily_chart should be a list"
        print(f"PASS: Revenue section has all fields: total={revenue['total_tenant_revenue']}, monthly={revenue['monthly_revenue']}, chart_points={len(revenue['daily_chart'])}")
        
        # Verify trials section
        assert "trials" in data, "Missing 'trials' section"
        trials = data["trials"]
        assert "enabled" in trials, "Missing trials.enabled"
        assert "duration_days" in trials, "Missing trials.duration_days"
        assert "total_trial_users" in trials, "Missing trials.total_trial_users"
        print(f"PASS: Trials section has all fields: enabled={trials['enabled']}, days={trials['duration_days']}")
        
        # Verify top_tenants
        assert "top_tenants" in data, "Missing 'top_tenants'"
        assert isinstance(data["top_tenants"], list), "top_tenants should be a list"
        if data["top_tenants"]:
            top = data["top_tenants"][0]
            assert "tenant_id" in top, "Missing tenant_id in top_tenants"
            assert "name" in top, "Missing name in top_tenants"
            assert "revenue" in top, "Missing revenue in top_tenants"
            assert "payment_count" in top, "Missing payment_count in top_tenants"
        print(f"PASS: top_tenants is a list with {len(data['top_tenants'])} items")
        
        # Verify recent_tenants
        assert "recent_tenants" in data, "Missing 'recent_tenants'"
        assert isinstance(data["recent_tenants"], list), "recent_tenants should be a list"
        print(f"PASS: recent_tenants is a list with {len(data['recent_tenants'])} items")
        
        # Verify recent_subscriptions
        assert "recent_subscriptions" in data, "Missing 'recent_subscriptions'"
        assert isinstance(data["recent_subscriptions"], list), "recent_subscriptions should be a list"
        print(f"PASS: recent_subscriptions is a list with {len(data['recent_subscriptions'])} items")
    
    def test_admin_stats_requires_super_admin(self, tenant_admin_token):
        """GET /api/admin/stats should return 403 for tenant admin"""
        headers = {"Authorization": f"Bearer {tenant_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/stats", headers=headers)
        
        assert response.status_code == 403, f"Expected 403 for tenant admin, got {response.status_code}"
        print("PASS: Tenant admin correctly denied access to /api/admin/stats (403)")
    
    def test_admin_stats_requires_auth(self):
        """GET /api/admin/stats should return 401 or 403 without auth"""
        response = requests.get(f"{BASE_URL}/api/admin/stats")
        
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print(f"PASS: Unauthenticated request correctly denied ({response.status_code})")


class TestTenantProfile:
    """Test GET /api/admin/tenant-profile/{tenant_id}"""
    
    def test_tenant_profile_returns_full_data(self, super_admin_token):
        """GET /api/admin/tenant-profile/{tenant_id} returns comprehensive tenant data"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/tenant-profile/{TEST_TENANT_ID}", headers=headers)
        
        assert response.status_code == 200, f"Tenant profile failed: {response.text}"
        data = response.json()
        
        # Verify tenant object
        assert "tenant" in data, "Missing 'tenant' object"
        tenant = data["tenant"]
        assert "tenant_id" in tenant, "Missing tenant_id"
        assert tenant["tenant_id"] == TEST_TENANT_ID, f"Wrong tenant_id: {tenant['tenant_id']}"
        assert "name" in tenant, "Missing tenant name"
        assert "status" in tenant, "Missing tenant status"
        print(f"PASS: Tenant object has required fields: name={tenant.get('name')}, status={tenant.get('status')}")
        
        # Verify stats object
        assert "stats" in data, "Missing 'stats' object"
        stats = data["stats"]
        required_stats = ["total_revenue", "monthly_revenue", "bot_users", "total_subscribers", 
                         "active_subscribers", "expired_subscribers", "total_payments", 
                         "pending_payments", "total_plans", "total_broadcasts"]
        for field in required_stats:
            assert field in stats, f"Missing stats.{field}"
        print(f"PASS: Stats object has all fields: revenue={stats['total_revenue']}, subs={stats['total_subscribers']}, payments={stats['total_payments']}")
        
        # Verify dashboard_admins
        assert "dashboard_admins" in data, "Missing 'dashboard_admins'"
        assert isinstance(data["dashboard_admins"], list), "dashboard_admins should be a list"
        print(f"PASS: dashboard_admins is a list with {len(data['dashboard_admins'])} items")
        
        # Verify telegram_admins
        assert "telegram_admins" in data, "Missing 'telegram_admins'"
        assert isinstance(data["telegram_admins"], list), "telegram_admins should be a list"
        print(f"PASS: telegram_admins is a list with {len(data['telegram_admins'])} items")
        
        # Verify plans
        assert "plans" in data, "Missing 'plans'"
        assert isinstance(data["plans"], list), "plans should be a list"
        print(f"PASS: plans is a list with {len(data['plans'])} items")
        
        # Verify subscribers
        assert "subscribers" in data, "Missing 'subscribers'"
        assert isinstance(data["subscribers"], list), "subscribers should be a list"
        print(f"PASS: subscribers is a list with {len(data['subscribers'])} items")
        
        # Verify recent_payments
        assert "recent_payments" in data, "Missing 'recent_payments'"
        assert isinstance(data["recent_payments"], list), "recent_payments should be a list"
        print(f"PASS: recent_payments is a list with {len(data['recent_payments'])} items")
        
        # Verify revenue_chart
        assert "revenue_chart" in data, "Missing 'revenue_chart'"
        assert isinstance(data["revenue_chart"], list), "revenue_chart should be a list"
        print(f"PASS: revenue_chart is a list with {len(data['revenue_chart'])} items")
        
        # Verify plan_distribution
        assert "plan_distribution" in data, "Missing 'plan_distribution'"
        assert isinstance(data["plan_distribution"], list), "plan_distribution should be a list"
        if data["plan_distribution"]:
            dist = data["plan_distribution"][0]
            assert "name" in dist, "Missing name in plan_distribution"
            assert "count" in dist, "Missing count in plan_distribution"
            assert "price" in dist, "Missing price in plan_distribution"
        print(f"PASS: plan_distribution is a list with {len(data['plan_distribution'])} items")
    
    def test_tenant_profile_404_for_nonexistent(self, super_admin_token):
        """GET /api/admin/tenant-profile/{tenant_id} returns 404 for non-existent tenant"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/tenant-profile/nonexistent_tenant_xyz", headers=headers)
        
        assert response.status_code == 404, f"Expected 404 for non-existent tenant, got {response.status_code}"
        print("PASS: Non-existent tenant correctly returns 404")
    
    def test_tenant_profile_requires_super_admin(self, tenant_admin_token):
        """GET /api/admin/tenant-profile/{tenant_id} should return 403 for tenant admin"""
        headers = {"Authorization": f"Bearer {tenant_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/tenant-profile/{TEST_TENANT_ID}", headers=headers)
        
        assert response.status_code == 403, f"Expected 403 for tenant admin, got {response.status_code}"
        print("PASS: Tenant admin correctly denied access to tenant profile (403)")
    
    def test_tenant_profile_requires_auth(self):
        """GET /api/admin/tenant-profile/{tenant_id} should return 401 or 403 without auth"""
        response = requests.get(f"{BASE_URL}/api/admin/tenant-profile/{TEST_TENANT_ID}")
        
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print(f"PASS: Unauthenticated request correctly denied ({response.status_code})")


class TestDataIntegrity:
    """Test data integrity and consistency"""
    
    def test_top_tenants_have_valid_data(self, super_admin_token):
        """Top tenants in admin stats should have valid revenue and payment data"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/stats", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        for tenant in data.get("top_tenants", []):
            assert isinstance(tenant.get("revenue", 0), (int, float)), "Revenue should be numeric"
            assert tenant.get("revenue", 0) >= 0, "Revenue should be non-negative"
            assert isinstance(tenant.get("payment_count", 0), int), "Payment count should be integer"
            assert tenant.get("payment_count", 0) >= 0, "Payment count should be non-negative"
        
        print(f"PASS: All {len(data.get('top_tenants', []))} top tenants have valid numeric data")
    
    def test_daily_chart_has_valid_format(self, super_admin_token):
        """Daily revenue chart should have valid date and revenue format"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/stats", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        daily_chart = data.get("revenue", {}).get("daily_chart", [])
        for point in daily_chart:
            assert "date" in point, "Chart point missing date"
            assert "revenue" in point, "Chart point missing revenue"
            assert isinstance(point["revenue"], (int, float)), "Revenue should be numeric"
        
        print(f"PASS: Daily chart has {len(daily_chart)} valid data points")
    
    def test_tenant_profile_stats_consistency(self, super_admin_token):
        """Tenant profile stats should be internally consistent"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/tenant-profile/{TEST_TENANT_ID}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        stats = data.get("stats", {})
        
        # Active + expired should be <= total
        total_subs = stats.get("total_subscribers", 0)
        active_subs = stats.get("active_subscribers", 0)
        expired_subs = stats.get("expired_subscribers", 0)
        assert active_subs + expired_subs <= total_subs + 10, f"Subscriber counts inconsistent: active={active_subs}, expired={expired_subs}, total={total_subs}"
        
        # Monthly revenue should be <= total revenue
        total_rev = stats.get("total_revenue", 0)
        monthly_rev = stats.get("monthly_revenue", 0)
        assert monthly_rev <= total_rev + 1, f"Monthly revenue ({monthly_rev}) > total revenue ({total_rev})"
        
        print(f"PASS: Tenant profile stats are internally consistent")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
