"""
Iteration 27: Tenant Data Isolation Security Tests
Tests the P0 bug fix for tenant data leaking between tenants.

Key fixes tested:
1. get_user_tenant() returns '__no_tenant__' for users without tenant_id
2. tq() function properly filters by tenant_id
3. Registration auto-creates unique tenants
4. Super admin can see all data (no regression)
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"
SUPER_ADMIN_PASSWORD = "Sumit@8958"
TENANT_ADMIN_EMAIL = "anamika@test.com"
TENANT_ADMIN_PASSWORD = "Admin123"
NEW_USER_EMAIL = "newtest_leak@example.com"
NEW_USER_PASSWORD = "Test123!"


class TestTenantIsolation:
    """Critical tenant data isolation tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_token(self, email, password):
        """Helper to get auth token"""
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password
        })
        if resp.status_code == 200:
            return resp.json().get("token")
        return None
    
    def test_01_super_admin_login(self):
        """Super admin can login"""
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["role"] == "super_admin"
        assert data["user"]["email"] == SUPER_ADMIN_EMAIL
    
    def test_02_tenant_admin_login(self):
        """Tenant admin can login with correct tenant_id"""
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["tenant_id"] == "tenant_85ee971d0285"
        assert data["user"]["role"] == "tenant_admin"
    
    def test_03_new_user_login(self):
        """New test user can login with their own tenant_id"""
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": NEW_USER_EMAIL,
            "password": NEW_USER_PASSWORD
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["tenant_id"].startswith("tenant_")
        assert data["user"]["tenant_id"] != "tenant_85ee971d0285"  # Different from Anamika
    
    def test_04_super_admin_sees_all_data(self):
        """Super admin /api/admin/stats returns all platform data"""
        token = self.get_token(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
        assert token is not None
        
        resp = self.session.get(f"{BASE_URL}/api/admin/stats", 
                                headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        
        # Super admin should see platform-wide stats
        assert "platform" in data
        assert "bot_ecosystem" in data
        assert "revenue" in data
        
        # Should have data (not empty)
        assert data["platform"]["total_tenants"] >= 1
        assert data["bot_ecosystem"]["total_payments"] >= 1
        assert data["revenue"]["total_tenant_revenue"] > 0
    
    def test_05_tenant_admin_sees_only_own_data(self):
        """Tenant admin analytics returns only their tenant's data"""
        token = self.get_token(TENANT_ADMIN_EMAIL, TENANT_ADMIN_PASSWORD)
        assert token is not None
        
        resp = self.session.get(f"{BASE_URL}/api/analytics",
                                headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        
        # Anamika's tenant has data
        assert data["total_subscribers"] > 0
        assert data["total_revenue"] > 0
        
        # Verify all recent_subscribers belong to tenant_85ee971d0285
        for sub in data.get("recent_subscribers", []):
            assert sub.get("tenant_id") == "tenant_85ee971d0285"
        
        # Verify all recent_payments belong to tenant_85ee971d0285
        for pay in data.get("recent_payments", []):
            assert pay.get("tenant_id") == "tenant_85ee971d0285"
    
    def test_06_new_user_sees_zero_data_critical(self):
        """CRITICAL: New user analytics returns 0 revenue, 0 subscribers (no data leak)"""
        token = self.get_token(NEW_USER_EMAIL, NEW_USER_PASSWORD)
        assert token is not None
        
        resp = self.session.get(f"{BASE_URL}/api/analytics",
                                headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        
        # CRITICAL ASSERTIONS - No data leak
        assert data["total_subscribers"] == 0, "Data leak: new user sees subscribers"
        assert data["active_subscribers"] == 0, "Data leak: new user sees active subs"
        assert data["total_revenue"] == 0, "Data leak: new user sees revenue"
        assert data["monthly_revenue"] == 0, "Data leak: new user sees monthly revenue"
        assert len(data["recent_subscribers"]) == 0, "Data leak: new user sees recent subs"
        assert len(data["recent_payments"]) == 0, "Data leak: new user sees recent payments"
        assert len(data["plan_stats"]) == 0, "Data leak: new user sees plan stats"
    
    def test_07_new_user_plans_empty(self):
        """New user /api/plans returns empty array"""
        token = self.get_token(NEW_USER_EMAIL, NEW_USER_PASSWORD)
        assert token is not None
        
        resp = self.session.get(f"{BASE_URL}/api/plans",
                                headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 0, "Data leak: new user sees plans from other tenants"
    
    def test_08_new_user_payments_empty(self):
        """New user /api/payments returns empty array"""
        token = self.get_token(NEW_USER_EMAIL, NEW_USER_PASSWORD)
        assert token is not None
        
        resp = self.session.get(f"{BASE_URL}/api/payments",
                                headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 0, "Data leak: new user sees payments from other tenants"
    
    def test_09_new_user_subscribers_empty(self):
        """New user /api/subscribers returns empty array"""
        token = self.get_token(NEW_USER_EMAIL, NEW_USER_PASSWORD)
        assert token is not None
        
        resp = self.session.get(f"{BASE_URL}/api/subscribers",
                                headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 0, "Data leak: new user sees subscribers from other tenants"
    
    def test_10_tenant_admin_has_plans(self):
        """Tenant admin /api/plans returns their plans"""
        token = self.get_token(TENANT_ADMIN_EMAIL, TENANT_ADMIN_PASSWORD)
        assert token is not None
        
        resp = self.session.get(f"{BASE_URL}/api/plans",
                                headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Tenant admin should see their plans"
        
        # Verify plans have expected structure (tenant_id is filtered server-side)
        for plan in data:
            assert "id" in plan
            assert "name" in plan
            assert "price" in plan
    
    def test_11_tenant_admin_has_payments(self):
        """Tenant admin /api/payments returns their payments"""
        token = self.get_token(TENANT_ADMIN_EMAIL, TENANT_ADMIN_PASSWORD)
        assert token is not None
        
        resp = self.session.get(f"{BASE_URL}/api/payments",
                                headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Tenant admin should see their payments"
    
    def test_12_tenant_admin_has_subscribers(self):
        """Tenant admin /api/subscribers returns their subscribers"""
        token = self.get_token(TENANT_ADMIN_EMAIL, TENANT_ADMIN_PASSWORD)
        assert token is not None
        
        resp = self.session.get(f"{BASE_URL}/api/subscribers",
                                headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Tenant admin should see their subscribers"


class TestRegistrationAutoTenant:
    """Tests for registration auto-creating unique tenants"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_13_registration_creates_unique_tenant(self):
        """Registration auto-creates unique tenant_id and sets role=tenant_owner"""
        random_email = f"test_isolation_{uuid.uuid4().hex[:8]}@test.com"
        
        resp = self.session.post(f"{BASE_URL}/api/auth/register", json={
            "email": random_email,
            "password": "TestPass123",
            "name": "Isolation Test User"
        })
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify response structure
        assert "token" in data
        assert "user" in data
        
        user = data["user"]
        assert user["email"] == random_email
        assert user["role"] == "tenant_owner"
        assert user["tenant_id"].startswith("tenant_")
        assert len(user["tenant_id"]) > 10  # tenant_xxxxxxxxxxxx format
        assert user["is_admin"] == True
    
    def test_14_new_registered_user_sees_zero_data(self):
        """Newly registered user sees 0 data (no leak from other tenants)"""
        random_email = f"test_isolation_{uuid.uuid4().hex[:8]}@test.com"
        
        # Register
        resp = self.session.post(f"{BASE_URL}/api/auth/register", json={
            "email": random_email,
            "password": "TestPass123",
            "name": "Fresh User"
        })
        assert resp.status_code == 200
        token = resp.json().get("token")
        
        # Check analytics
        resp = self.session.get(f"{BASE_URL}/api/analytics",
                                headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        
        # CRITICAL: No data leak
        assert data["total_subscribers"] == 0
        assert data["total_revenue"] == 0
        assert len(data["recent_subscribers"]) == 0
        assert len(data["recent_payments"]) == 0
    
    def test_15_two_registrations_get_different_tenants(self):
        """Two different registrations get different tenant_ids"""
        email1 = f"test_tenant1_{uuid.uuid4().hex[:8]}@test.com"
        email2 = f"test_tenant2_{uuid.uuid4().hex[:8]}@test.com"
        
        # Register first user
        resp1 = self.session.post(f"{BASE_URL}/api/auth/register", json={
            "email": email1,
            "password": "TestPass123",
            "name": "User 1"
        })
        assert resp1.status_code == 200
        tenant1 = resp1.json()["user"]["tenant_id"]
        
        # Register second user
        resp2 = self.session.post(f"{BASE_URL}/api/auth/register", json={
            "email": email2,
            "password": "TestPass123",
            "name": "User 2"
        })
        assert resp2.status_code == 200
        tenant2 = resp2.json()["user"]["tenant_id"]
        
        # Verify different tenant_ids
        assert tenant1 != tenant2, "Two users should get different tenant_ids"


class TestRevenueAnalyticsIsolation:
    """Tests for revenue analytics endpoint isolation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_token(self, email, password):
        """Helper to get auth token"""
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password
        })
        if resp.status_code == 200:
            return resp.json().get("token")
        return None
    
    def test_16_new_user_revenue_analytics_zero(self):
        """New user /api/analytics/revenue returns 0 total_revenue"""
        token = self.get_token(NEW_USER_EMAIL, NEW_USER_PASSWORD)
        assert token is not None
        
        resp = self.session.get(f"{BASE_URL}/api/analytics/revenue",
                                headers={"Authorization": f"Bearer {token}"})
        # This endpoint may not exist, skip if 404
        if resp.status_code == 404:
            pytest.skip("Revenue analytics endpoint not found")
        
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("total_revenue", 0) == 0, "Data leak: new user sees revenue"
    
    def test_17_tenant_admin_revenue_analytics_has_data(self):
        """Tenant admin /api/analytics/revenue returns their revenue"""
        token = self.get_token(TENANT_ADMIN_EMAIL, TENANT_ADMIN_PASSWORD)
        assert token is not None
        
        resp = self.session.get(f"{BASE_URL}/api/analytics/revenue",
                                headers={"Authorization": f"Bearer {token}"})
        # This endpoint may not exist, skip if 404
        if resp.status_code == 404:
            pytest.skip("Revenue analytics endpoint not found")
        
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("total_revenue", 0) > 0, "Tenant admin should see their revenue"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
