"""
Iteration 41: DDD (Domain-Driven Design) Backend Restructuring Tests

Tests the reorganized backend architecture:
- core/ (config, db, security, exceptions, constants)
- dependencies/ (auth, permissions)
- api/ (public/, tenant_admin/, platform_admin/, customer/, webhooks/)
- schemas/, middleware/, repositories/, workers/, scripts/

All APIs should work exactly as before with the new DDD structure.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"
SUPER_ADMIN_PASSWORD = "Sumit@8958"
TENANT_ADMIN_EMAIL = "anamika@test.com"
TENANT_ADMIN_PASSWORD = "Admin123"


class TestAuthRoutes:
    """Test auth routes from api/public/auth.py"""
    
    def test_login_tenant_admin_returns_token_and_refresh(self):
        """POST /api/auth/login returns both token and refresh_token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        
        # Verify token structure
        assert "token" in data, "Missing token in response"
        assert "refresh_token" in data, "Missing refresh_token in response"
        assert "user" in data, "Missing user in response"
        
        # Verify user data
        user = data["user"]
        assert user["email"] == TENANT_ADMIN_EMAIL
        assert user["role"] == "tenant_admin"
        assert "tenant_id" in user
        assert user["tenant_id"].startswith("tenant_")
        print(f"✓ Tenant admin login successful: {user['email']}, role={user['role']}")
    
    def test_login_super_admin_returns_token_and_refresh(self):
        """POST /api/auth/login for super admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Super admin login failed: {response.text}"
        data = response.json()
        
        assert "token" in data
        assert "refresh_token" in data
        assert data["user"]["role"] == "super_admin"
        print(f"✓ Super admin login successful: {data['user']['email']}")
    
    def test_login_invalid_credentials_returns_401(self):
        """POST /api/auth/login with wrong password returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("✓ Invalid credentials correctly rejected with 401")
    
    def test_token_refresh_works(self):
        """POST /api/auth/refresh with valid refresh_token returns new access token"""
        # First login to get refresh token
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200
        refresh_token = login_resp.json()["refresh_token"]
        
        # Use refresh token to get new access token
        refresh_resp = requests.post(f"{BASE_URL}/api/auth/refresh", json={
            "refresh_token": refresh_token
        })
        assert refresh_resp.status_code == 200, f"Refresh failed: {refresh_resp.text}"
        assert "token" in refresh_resp.json()
        print("✓ Token refresh works correctly")
    
    def test_auth_me_returns_user_info(self):
        """GET /api/auth/me returns current user info"""
        # Login first
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        token = login_resp.json()["token"]
        
        # Get user info
        me_resp = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert me_resp.status_code == 200
        user = me_resp.json()
        assert user["email"] == TENANT_ADMIN_EMAIL
        assert user["role"] == "tenant_admin"
        print(f"✓ GET /api/auth/me returns correct user: {user['email']}")


class TestTenantAdminRoutes:
    """Test tenant admin routes from api/tenant_admin/"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as tenant admin before each test"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200
        self.token = login_resp.json()["token"]
        self.tenant_id = login_resp.json()["user"]["tenant_id"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_analytics(self):
        """GET /api/analytics returns subscriber and revenue data"""
        response = requests.get(f"{BASE_URL}/api/analytics", headers=self.headers)
        assert response.status_code == 200, f"Analytics failed: {response.text}"
        data = response.json()
        
        # Verify analytics structure
        assert "total_subscribers" in data
        assert "active_subscribers" in data
        assert "total_revenue" in data
        assert "monthly_revenue" in data
        print(f"✓ GET /api/analytics: {data['total_subscribers']} subscribers, Rs.{data['total_revenue']} revenue")
    
    def test_get_plans(self):
        """GET /api/plans returns plans for tenant"""
        response = requests.get(f"{BASE_URL}/api/plans", headers=self.headers)
        assert response.status_code == 200, f"Plans failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/plans: {len(data)} plans found")
    
    def test_get_subscribers(self):
        """GET /api/subscribers returns subscribers for tenant"""
        response = requests.get(f"{BASE_URL}/api/subscribers", headers=self.headers)
        assert response.status_code == 200, f"Subscribers failed: {response.text}"
        data = response.json()
        # Response can be list or dict with items
        if isinstance(data, dict):
            assert "items" in data or "subscribers" in data or isinstance(data.get("total"), int)
        print(f"✓ GET /api/subscribers: Response received")
    
    def test_get_broadcasts(self):
        """GET /api/broadcasts returns broadcasts for tenant"""
        response = requests.get(f"{BASE_URL}/api/broadcasts", headers=self.headers)
        assert response.status_code == 200, f"Broadcasts failed: {response.text}"
        data = response.json()
        assert isinstance(data, (list, dict))
        print(f"✓ GET /api/broadcasts: Response received")
    
    def test_get_templates(self):
        """GET /api/templates returns templates for tenant"""
        response = requests.get(f"{BASE_URL}/api/templates", headers=self.headers)
        assert response.status_code == 200, f"Templates failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/templates: {len(data)} templates found")
    
    def test_get_coupons(self):
        """GET /api/coupons returns coupons for tenant (engagement route)"""
        response = requests.get(f"{BASE_URL}/api/coupons", headers=self.headers)
        assert response.status_code == 200, f"Coupons failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/coupons: {len(data)} coupons found")
    
    def test_get_faqs(self):
        """GET /api/faqs returns FAQs for tenant (engagement route)"""
        response = requests.get(f"{BASE_URL}/api/faqs", headers=self.headers)
        assert response.status_code == 200, f"FAQs failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/faqs: {len(data)} FAQs found")
    
    def test_get_channels(self):
        """GET /api/channels returns channels for tenant (dashboard route)"""
        response = requests.get(f"{BASE_URL}/api/channels", headers=self.headers)
        assert response.status_code == 200, f"Channels failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/channels: {len(data)} channels found")
    
    def test_get_settings(self):
        """GET /api/settings returns bot settings"""
        response = requests.get(f"{BASE_URL}/api/settings", headers=self.headers)
        assert response.status_code == 200, f"Settings failed: {response.text}"
        data = response.json()
        assert isinstance(data, dict)
        print(f"✓ GET /api/settings: Settings retrieved")


class TestPlatformAdminRoutes:
    """Test platform admin routes from api/platform_admin/admin.py"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as super admin before each test"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200
        self.token = login_resp.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_saas_tenants(self):
        """GET /api/saas/tenants returns all tenants (platform_admin route)"""
        response = requests.get(f"{BASE_URL}/api/saas/tenants", headers=self.headers)
        assert response.status_code == 200, f"Tenants failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/saas/tenants: {len(data)} tenants found")
    
    def test_get_risk_alerts(self):
        """GET /api/admin/risk-alerts returns alerts (platform_admin route)"""
        # Try the correct endpoint path
        response = requests.get(f"{BASE_URL}/api/saas/risk-alerts", headers=self.headers)
        assert response.status_code == 200, f"Risk alerts failed: {response.text}"
        data = response.json()
        assert "alerts" in data or isinstance(data, list)
        print(f"✓ GET /api/saas/risk-alerts: Response received")
    
    def test_get_admin_stats(self):
        """GET /api/admin/stats returns platform stats"""
        response = requests.get(f"{BASE_URL}/api/admin/stats", headers=self.headers)
        assert response.status_code == 200, f"Admin stats failed: {response.text}"
        data = response.json()
        assert "platform" in data or "total_users" in data
        print(f"✓ GET /api/admin/stats: Platform stats retrieved")
    
    def test_get_tenant_admins(self):
        """GET /api/saas/tenant-admins returns all tenant admins"""
        response = requests.get(f"{BASE_URL}/api/saas/tenant-admins", headers=self.headers)
        assert response.status_code == 200, f"Tenant admins failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/saas/tenant-admins: {len(data)} tenant admins found")
    
    def test_get_trial_config(self):
        """GET /api/trial/config returns trial configuration"""
        response = requests.get(f"{BASE_URL}/api/trial/config", headers=self.headers)
        assert response.status_code == 200, f"Trial config failed: {response.text}"
        data = response.json()
        assert "enabled" in data or "duration_days" in data
        print(f"✓ GET /api/trial/config: Trial config retrieved")


class TestTenantIsolation:
    """Test that tenant admin can only see their own data"""
    
    def test_tenant_admin_denied_risk_alerts(self):
        """Tenant admin should be denied access to risk alerts (403)"""
        # Login as tenant admin
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        token = login_resp.json()["token"]
        
        # Try to access risk alerts
        response = requests.get(f"{BASE_URL}/api/saas/risk-alerts", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("✓ Tenant admin correctly denied access to risk alerts (403)")
    
    def test_tenant_admin_denied_saas_tenants(self):
        """Tenant admin should be denied access to saas/tenants (403)"""
        # Login as tenant admin
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        token = login_resp.json()["token"]
        
        # Try to access tenants list
        response = requests.get(f"{BASE_URL}/api/saas/tenants", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("✓ Tenant admin correctly denied access to saas/tenants (403)")
    
    def test_tenant_admin_can_access_own_analytics(self):
        """Tenant admin can access their own analytics"""
        # Login as tenant admin
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        token = login_resp.json()["token"]
        
        # Access analytics
        response = requests.get(f"{BASE_URL}/api/analytics", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        print("✓ Tenant admin can access their own analytics")


class TestBackwardCompatibility:
    """Test that old route paths still work via backward-compatible wrappers"""
    
    def test_auth_login_works(self):
        """Auth login endpoint works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        print("✓ /api/auth/login works")
    
    def test_plans_endpoint_works(self):
        """Plans endpoint works"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        token = login_resp.json()["token"]
        
        response = requests.get(f"{BASE_URL}/api/plans", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        print("✓ /api/plans works")
    
    def test_subscribers_endpoint_works(self):
        """Subscribers endpoint works"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        token = login_resp.json()["token"]
        
        response = requests.get(f"{BASE_URL}/api/subscribers", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        print("✓ /api/subscribers works")


class TestDDDStructureImports:
    """Verify DDD structure is working by testing key endpoints"""
    
    def test_core_config_loaded(self):
        """Verify core/config.py is loaded (JWT works)"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        # JWT token generation means config is loaded
        assert "token" in response.json()
        print("✓ core/config.py loaded (JWT works)")
    
    def test_core_db_connected(self):
        """Verify core/db.py is connected (data returned)"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        token = login_resp.json()["token"]
        
        response = requests.get(f"{BASE_URL}/api/analytics", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        # Analytics data means DB is connected
        data = response.json()
        assert "total_subscribers" in data
        print("✓ core/db.py connected (analytics data returned)")
    
    def test_dependencies_auth_works(self):
        """Verify dependencies/auth.py works (get_current_user)"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        token = login_resp.json()["token"]
        
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        assert response.json()["email"] == TENANT_ADMIN_EMAIL
        print("✓ dependencies/auth.py works (get_current_user)")
    
    def test_api_public_auth_works(self):
        """Verify api/public/auth.py works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        print("✓ api/public/auth.py works")
    
    def test_api_tenant_admin_dashboard_works(self):
        """Verify api/tenant_admin/dashboard.py works"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        token = login_resp.json()["token"]
        
        response = requests.get(f"{BASE_URL}/api/channels", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        print("✓ api/tenant_admin/dashboard.py works")
    
    def test_api_platform_admin_works(self):
        """Verify api/platform_admin/admin.py works"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        token = login_resp.json()["token"]
        
        response = requests.get(f"{BASE_URL}/api/admin/stats", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        print("✓ api/platform_admin/admin.py works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
