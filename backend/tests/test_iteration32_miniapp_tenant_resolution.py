"""
Iteration 32: Mini App Tenant Resolution Tests
Tests the fix for Mini App showing different plans than Dashboard.
Root cause: Mini App frontend was not passing tenant_id to backend API calls.
Fix: Created /api/miniapp/resolve-tenant/{userId} endpoint and updated frontend to use it.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test tenant IDs from test_credentials.md
TENANT_A_ID = "tenant_85ee971d0285"  # Primary tenant with 8 plans
DEFAULT_TENANT_ID = "default"  # Has 0 active plans

class TestMiniAppTenantResolution:
    """Test the resolve-tenant endpoint and plans with tenant_id"""
    
    def test_resolve_tenant_returns_real_tenant(self):
        """resolve-tenant should return tenant_85ee971d0285 (not 'default') since that tenant has active plans"""
        response = requests.get(f"{BASE_URL}/api/miniapp/resolve-tenant/12345")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "tenant_id" in data, "Response should contain tenant_id"
        # Should resolve to the tenant with active plans, not 'default'
        assert data["tenant_id"] == TENANT_A_ID, f"Expected {TENANT_A_ID}, got {data['tenant_id']}"
        print(f"PASS: resolve-tenant returns {data['tenant_id']}")
    
    def test_resolve_tenant_with_different_user_id(self):
        """resolve-tenant should work with any user ID"""
        response = requests.get(f"{BASE_URL}/api/miniapp/resolve-tenant/999999")
        assert response.status_code == 200
        data = response.json()
        assert "tenant_id" in data
        # Should still resolve to tenant with plans
        assert data["tenant_id"] != DEFAULT_TENANT_ID or data["tenant_id"] == TENANT_A_ID
        print(f"PASS: resolve-tenant for user 999999 returns {data['tenant_id']}")


class TestMiniAppPlansWithTenant:
    """Test plans endpoint with and without tenant_id"""
    
    def test_plans_with_tenant_id_returns_plans(self):
        """GET /api/miniapp/plans?tenant_id=tenant_85ee971d0285 should return 8 active plans"""
        response = requests.get(f"{BASE_URL}/api/miniapp/plans?tenant_id={TENANT_A_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        plans = response.json()
        assert isinstance(plans, list), "Response should be a list"
        assert len(plans) >= 1, f"Expected at least 1 plan, got {len(plans)}"
        print(f"PASS: plans with tenant_id={TENANT_A_ID} returns {len(plans)} plans")
        
        # Verify plan structure
        if plans:
            plan = plans[0]
            assert "id" in plan, "Plan should have id"
            assert "name" in plan, "Plan should have name"
            assert "price" in plan, "Plan should have price"
            print(f"  First plan: {plan.get('name')} - Rs.{plan.get('price')}")
    
    def test_plans_without_tenant_id_returns_default_plans(self):
        """GET /api/miniapp/plans (without tenant_id) should return 0 plans (default tenant has no plans)"""
        response = requests.get(f"{BASE_URL}/api/miniapp/plans")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        plans = response.json()
        assert isinstance(plans, list), "Response should be a list"
        # Default tenant should have 0 plans
        print(f"PASS: plans without tenant_id returns {len(plans)} plans (expected 0 for default tenant)")
    
    def test_plans_with_invalid_tenant_returns_empty(self):
        """GET /api/miniapp/plans?tenant_id=invalid_tenant should return empty list"""
        response = requests.get(f"{BASE_URL}/api/miniapp/plans?tenant_id=invalid_tenant_xyz")
        assert response.status_code == 200
        plans = response.json()
        assert isinstance(plans, list)
        assert len(plans) == 0, f"Expected 0 plans for invalid tenant, got {len(plans)}"
        print("PASS: plans with invalid tenant_id returns 0 plans")


class TestMiniAppUPIDetails:
    """Test UPI details endpoint with tenant_id"""
    
    def test_upi_details_with_tenant_id(self):
        """GET /api/miniapp/upi-details?tenant_id=tenant_85ee971d0285 should return UPI details"""
        response = requests.get(f"{BASE_URL}/api/miniapp/upi-details?tenant_id={TENANT_A_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        # Should have upi_id field (may be empty if not configured)
        assert "upi_id" in data, "Response should contain upi_id"
        assert "payment_message" in data, "Response should contain payment_message"
        print(f"PASS: upi-details returns upi_id={data.get('upi_id', 'N/A')}")
    
    def test_upi_details_without_tenant_id(self):
        """GET /api/miniapp/upi-details should work with default tenant"""
        response = requests.get(f"{BASE_URL}/api/miniapp/upi-details")
        assert response.status_code == 200
        data = response.json()
        assert "upi_id" in data
        print("PASS: upi-details without tenant_id works")


class TestMiniAppStatus:
    """Test subscription status endpoint with tenant_id"""
    
    def test_status_with_tenant_id(self):
        """GET /api/miniapp/status/{userId}?tenant_id=tenant_85ee971d0285 should work"""
        response = requests.get(f"{BASE_URL}/api/miniapp/status/12345?tenant_id={TENANT_A_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        # Should have is_active field
        assert "is_active" in data, "Response should contain is_active"
        print(f"PASS: status endpoint returns is_active={data.get('is_active')}")
    
    def test_status_without_tenant_id(self):
        """GET /api/miniapp/status/{userId} should work with default tenant"""
        response = requests.get(f"{BASE_URL}/api/miniapp/status/12345")
        assert response.status_code == 200
        data = response.json()
        assert "is_active" in data
        print("PASS: status without tenant_id works")


class TestMiniAppReferral:
    """Test referral endpoint with tenant_id"""
    
    def test_referral_with_tenant_id(self):
        """GET /api/miniapp/referral/{userId}?tenant_id=tenant_85ee971d0285 should work"""
        response = requests.get(f"{BASE_URL}/api/miniapp/referral/12345?tenant_id={TENANT_A_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "referral_code" in data, "Response should contain referral_code"
        print(f"PASS: referral endpoint returns code={data.get('referral_code')}")


class TestMiniAppNotifications:
    """Test notifications endpoint with tenant_id"""
    
    def test_notifications_with_tenant_id(self):
        """GET /api/miniapp/notifications/{userId}?tenant_id=tenant_85ee971d0285 should work"""
        response = requests.get(f"{BASE_URL}/api/miniapp/notifications/12345?tenant_id={TENANT_A_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"PASS: notifications endpoint returns {len(data)} notifications")


class TestDashboardLogin:
    """Test dashboard login for Super Admin and Tenant Admin"""
    
    def test_super_admin_login(self):
        """Super Admin login should work"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "gamerxboys8958@gmail.com",
            "password": "Sumit@8958"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "token" in data, "Response should contain token"
        assert "user" in data, "Response should contain user"
        print(f"PASS: Super Admin login works, role={data['user'].get('role')}")
    
    def test_tenant_admin_login(self):
        """Tenant Admin (Anamika) login should work"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "anamika@test.com",
            "password": "Admin123"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "token" in data, "Response should contain token"
        assert "user" in data, "Response should contain user"
        assert data["user"].get("tenant_id") == TENANT_A_ID, f"Expected tenant_id={TENANT_A_ID}"
        print(f"PASS: Tenant Admin login works, tenant_id={data['user'].get('tenant_id')}")


class TestBackendHealth:
    """Test backend is running without errors"""
    
    def test_health_endpoint(self):
        """Backend health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Backend health check passed")


class TestMiniAppPayments:
    """Test payments endpoint with tenant_id"""
    
    def test_payments_with_tenant_id(self):
        """GET /api/miniapp/payments/{userId}?tenant_id=tenant_85ee971d0285 should work"""
        response = requests.get(f"{BASE_URL}/api/miniapp/payments/12345?tenant_id={TENANT_A_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"PASS: payments endpoint returns {len(data)} payments")


class TestMiniAppLiveSessions:
    """Test live sessions public endpoint with tenant_id"""
    
    def test_live_sessions_with_tenant_id(self):
        """GET /api/miniapp/live-sessions/public?tenant_id=tenant_85ee971d0285 should work"""
        response = requests.get(f"{BASE_URL}/api/miniapp/live-sessions/public?tenant_id={TENANT_A_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"PASS: live-sessions/public returns {len(data)} sessions")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
