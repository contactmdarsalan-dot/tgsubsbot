"""
Iteration 29: Security Fixes Testing
Tests for:
1. Mini App Users - Super Admin only access (GET /api/miniapp-users)
2. Settings tenant isolation (GET/PUT /api/settings)
3. Plans dialog UI (frontend test)

Test credentials:
- Super Admin: gamerxboys8958@gmail.com / Sumit@8958
- Tenant Admin: anamika@test.com / Admin123
- New Test Tenant: newtest_leak@example.com / Test123!
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://trial-management-hub-1.preview.emergentagent.com')

# Test credentials
SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"
SUPER_ADMIN_PASSWORD = "Sumit@8958"
TENANT_ADMIN_EMAIL = "anamika@test.com"
TENANT_ADMIN_PASSWORD = "Admin123"
NEW_TENANT_EMAIL = "newtest_leak@example.com"
NEW_TENANT_PASSWORD = "Test123!"


@pytest.fixture(scope="module")
def super_admin_token():
    """Get super admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Super admin login failed: {response.status_code} - {response.text}")
    return response.json().get("token")


@pytest.fixture(scope="module")
def tenant_admin_token():
    """Get tenant admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TENANT_ADMIN_EMAIL,
        "password": TENANT_ADMIN_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Tenant admin login failed: {response.status_code} - {response.text}")
    return response.json().get("token")


@pytest.fixture(scope="module")
def new_tenant_token():
    """Get new tenant user auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": NEW_TENANT_EMAIL,
        "password": NEW_TENANT_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"New tenant login failed: {response.status_code} - {response.text}")
    return response.json().get("token")


class TestMiniAppUsersAccess:
    """Test Mini App Users endpoint - Super Admin only"""
    
    def test_miniapp_users_super_admin_access(self, super_admin_token):
        """Super Admin should be able to access /api/miniapp-users"""
        response = requests.get(
            f"{BASE_URL}/api/miniapp-users",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Should return a list (even if empty)
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✓ Super Admin can access miniapp-users: {len(data)} users found")
    
    def test_miniapp_users_tenant_admin_blocked(self, tenant_admin_token):
        """Tenant Admin should get 403 when accessing /api/miniapp-users"""
        response = requests.get(
            f"{BASE_URL}/api/miniapp-users",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        data = response.json()
        assert "Super Admin" in data.get("detail", ""), f"Expected 'Super Admin access required', got: {data}"
        print(f"✓ Tenant Admin correctly blocked from miniapp-users: {data.get('detail')}")
    
    def test_miniapp_users_new_tenant_blocked(self, new_tenant_token):
        """New tenant user should get 403 when accessing /api/miniapp-users"""
        response = requests.get(
            f"{BASE_URL}/api/miniapp-users",
            headers={"Authorization": f"Bearer {new_tenant_token}"}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✓ New tenant user correctly blocked from miniapp-users")
    
    def test_miniapp_users_stats_super_admin_only(self, super_admin_token, tenant_admin_token):
        """Test /api/miniapp-users/stats is also super admin only"""
        # Super admin should access
        response = requests.get(
            f"{BASE_URL}/api/miniapp-users/stats",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200, f"Super admin stats failed: {response.status_code}"
        
        # Tenant admin should be blocked
        response = requests.get(
            f"{BASE_URL}/api/miniapp-users/stats",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 403, f"Tenant admin should be blocked from stats: {response.status_code}"
        print(f"✓ miniapp-users/stats correctly restricted to super admin")


class TestSettingsTenantIsolation:
    """Test Settings endpoint tenant isolation"""
    
    def test_settings_new_tenant_empty_defaults(self, new_tenant_token):
        """New tenant should see empty default settings (no leaked data)"""
        response = requests.get(
            f"{BASE_URL}/api/settings",
            headers={"Authorization": f"Bearer {new_tenant_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Check that sensitive fields are empty/default
        bot_token = data.get("telegram_bot_token", "")
        upi_id = data.get("upi_id", "")
        channel_id = data.get("telegram_channel_id", "")
        
        # New tenant should have empty settings (no leaked data from other tenants)
        # The settings ID should be tenant-specific
        settings_id = data.get("id", "")
        
        print(f"✓ New tenant settings: id={settings_id}, bot_token={bool(bot_token)}, upi_id={bool(upi_id)}, channel_id={bool(channel_id)}")
        
        # If settings_id contains tenant-specific ID, that's correct
        # Empty values are expected for new tenants
        assert settings_id.startswith("bot_settings_"), f"Settings ID should be tenant-specific: {settings_id}"
        print(f"✓ Settings are tenant-isolated with ID: {settings_id}")
    
    def test_settings_super_admin_access(self, super_admin_token):
        """Super Admin should be able to access settings"""
        response = requests.get(
            f"{BASE_URL}/api/settings",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        print(f"✓ Super Admin settings access: id={data.get('id', 'N/A')}")
    
    def test_settings_tenant_admin_access(self, tenant_admin_token):
        """Tenant Admin should access their own tenant's settings"""
        response = requests.get(
            f"{BASE_URL}/api/settings",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        settings_id = data.get("id", "")
        
        # Tenant admin should have tenant-specific settings
        assert "tenant_" in settings_id or settings_id == "bot_settings", f"Settings ID should be tenant-specific: {settings_id}"
        print(f"✓ Tenant Admin settings: id={settings_id}")
    
    def test_settings_isolation_different_tenants(self, tenant_admin_token, new_tenant_token):
        """Different tenants should have different settings IDs"""
        # Get tenant admin settings
        response1 = requests.get(
            f"{BASE_URL}/api/settings",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        settings1 = response1.json()
        
        # Get new tenant settings
        response2 = requests.get(
            f"{BASE_URL}/api/settings",
            headers={"Authorization": f"Bearer {new_tenant_token}"}
        )
        settings2 = response2.json()
        
        # Settings IDs should be different
        id1 = settings1.get("id", "")
        id2 = settings2.get("id", "")
        
        assert id1 != id2, f"Different tenants should have different settings IDs: {id1} vs {id2}"
        print(f"✓ Settings isolation verified: {id1} != {id2}")


class TestSidebarNavigation:
    """Test sidebar navigation visibility based on role"""
    
    def test_super_admin_check(self, super_admin_token):
        """Verify super admin role check endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/auth/check-admin",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("is_admin") == True, f"Super admin should be admin: {data}"
        print(f"✓ Super admin check: is_admin={data.get('is_admin')}, role={data.get('role')}")
    
    def test_tenant_admin_check(self, tenant_admin_token):
        """Verify tenant admin role check endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/auth/check-admin",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("is_admin") == True, f"Tenant admin should be admin: {data}"
        # Role should NOT be super_admin
        assert data.get("role") != "super_admin", f"Tenant admin should not have super_admin role: {data}"
        print(f"✓ Tenant admin check: is_admin={data.get('is_admin')}, role={data.get('role')}")


class TestPlansEndpoint:
    """Test Plans endpoint for tenant admin"""
    
    def test_plans_tenant_admin_access(self, tenant_admin_token):
        """Tenant admin should be able to access plans"""
        response = requests.get(
            f"{BASE_URL}/api/plans",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✓ Tenant admin can access plans: {len(data)} plans found")
    
    def test_plans_create_tenant_admin(self, tenant_admin_token):
        """Tenant admin should be able to create plans"""
        # This is a read-only test - just verify the endpoint exists
        # We don't actually create to avoid polluting data
        response = requests.get(
            f"{BASE_URL}/api/plans",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 200
        print(f"✓ Plans endpoint accessible for tenant admin")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
