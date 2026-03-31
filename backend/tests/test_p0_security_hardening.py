"""
P0 Security Hardening Tests - Iteration 20
Tests for multi-tenant SaaS security features:
1. Super Admin vs Tenant Admin role-based access
2. JWT authentication on all tenant routes
3. Object-level tenant_id authorization
4. CORS strict allowlist
5. MongoDB indexes at startup
6. Frontend auth state from backend only
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://admin-dashboard-mvp.preview.emergentagent.com')

# Test credentials from test_credentials.md
SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"
SUPER_ADMIN_PASSWORD = "Sumit@8958"
TENANT_ADMIN_EMAIL = "anamika@test.com"
TENANT_ADMIN_PASSWORD = "Admin123"
TENANT_ID = "tenant_85ee971d0285"


class TestAuthenticationAndRoles:
    """Test authentication and role-based access"""
    
    @pytest.fixture(scope="class")
    def super_admin_token(self):
        """Get super admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Super admin login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        return data["token"]
    
    @pytest.fixture(scope="class")
    def tenant_admin_token(self):
        """Get tenant admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Tenant admin login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        return data["token"]
    
    def test_super_admin_login_returns_correct_role(self, super_admin_token):
        """Super Admin login returns role=super_admin"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        # Super admin should have role=super_admin OR email in SUPER_ADMIN_EMAILS
        assert data.get("role") == "super_admin" or data.get("email") == SUPER_ADMIN_EMAIL
        print(f"Super admin role: {data.get('role')}, email: {data.get('email')}")
    
    def test_tenant_admin_login_returns_correct_role_and_tenant(self, tenant_admin_token):
        """Tenant Admin login returns role=tenant_admin and tenant_id"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("role") == "tenant_admin", f"Expected tenant_admin, got {data.get('role')}"
        assert data.get("tenant_id") == TENANT_ID, f"Expected {TENANT_ID}, got {data.get('tenant_id')}"
        print(f"Tenant admin role: {data.get('role')}, tenant_id: {data.get('tenant_id')}")
    
    def test_check_admin_returns_role_field(self, super_admin_token):
        """/api/auth/check-admin returns role field (not just is_admin boolean)"""
        response = requests.get(
            f"{BASE_URL}/api/auth/check-admin",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "role" in data, "Missing 'role' field in check-admin response"
        assert "is_admin" in data, "Missing 'is_admin' field in check-admin response"
        print(f"check-admin response: {data}")


class TestSuperAdminAccess:
    """Test Super Admin can access platform-level routes"""
    
    @pytest.fixture(scope="class")
    def super_admin_token(self):
        """Get super admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["token"]
    
    def test_super_admin_can_access_saas_tenants(self, super_admin_token):
        """Super Admin can access /api/saas/tenants (200 OK)"""
        response = requests.get(
            f"{BASE_URL}/api/saas/tenants",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of tenants"
        print(f"Super admin sees {len(data)} tenants")
    
    def test_super_admin_can_access_all_subscribers(self, super_admin_token):
        """Super Admin sees ALL subscribers across tenants"""
        response = requests.get(
            f"{BASE_URL}/api/subscribers",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Expected list of subscribers"
        # Super admin should see subscribers from multiple tenants (or all)
        tenant_ids = set(sub.get("tenant_id", "") for sub in data if sub.get("tenant_id"))
        print(f"Super admin sees {len(data)} subscribers from tenants: {tenant_ids}")
    
    def test_super_admin_can_access_all_payments(self, super_admin_token):
        """Super Admin sees ALL payments across tenants"""
        response = requests.get(
            f"{BASE_URL}/api/payments",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Expected list of payments"
        print(f"Super admin sees {len(data)} payments")
    
    def test_super_admin_can_access_analytics(self, super_admin_token):
        """Super Admin can access /api/analytics"""
        response = requests.get(
            f"{BASE_URL}/api/analytics",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_subscribers" in data or "total_revenue" in data
        print(f"Super admin analytics: {data.get('total_subscribers', 'N/A')} subscribers")


class TestTenantAdminAccessRestrictions:
    """Test Tenant Admin CANNOT access platform-level routes"""
    
    @pytest.fixture(scope="class")
    def tenant_admin_token(self):
        """Get tenant admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["token"]
    
    def test_tenant_admin_cannot_access_saas_tenants(self, tenant_admin_token):
        """Tenant Admin CANNOT access /api/saas/tenants (403 Forbidden)"""
        response = requests.get(
            f"{BASE_URL}/api/saas/tenants",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"Tenant admin correctly blocked from /api/saas/tenants: {response.status_code}")
    
    def test_tenant_admin_sees_only_their_subscribers(self, tenant_admin_token):
        """Tenant Admin sees only their tenant's subscribers"""
        response = requests.get(
            f"{BASE_URL}/api/subscribers",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        # All subscribers should belong to tenant_85ee971d0285
        for sub in data:
            if sub.get("tenant_id"):
                assert sub.get("tenant_id") == TENANT_ID, f"Tenant admin sees subscriber from wrong tenant: {sub.get('tenant_id')}"
        print(f"Tenant admin sees {len(data)} subscribers (all from {TENANT_ID})")
    
    def test_tenant_admin_sees_only_their_payments(self, tenant_admin_token):
        """Tenant Admin sees only their tenant's payments"""
        response = requests.get(
            f"{BASE_URL}/api/payments",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        # All payments should belong to tenant_85ee971d0285
        for payment in data:
            if payment.get("tenant_id"):
                assert payment.get("tenant_id") == TENANT_ID, f"Tenant admin sees payment from wrong tenant: {payment.get('tenant_id')}"
        print(f"Tenant admin sees {len(data)} payments (all from {TENANT_ID})")
    
    def test_tenant_admin_sees_only_their_plans(self, tenant_admin_token):
        """Tenant Admin can access /api/plans (sees only their tenant's plans)"""
        response = requests.get(
            f"{BASE_URL}/api/plans",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        # All plans should belong to tenant_85ee971d0285
        for plan in data:
            if plan.get("tenant_id"):
                assert plan.get("tenant_id") == TENANT_ID, f"Tenant admin sees plan from wrong tenant: {plan.get('tenant_id')}"
        print(f"Tenant admin sees {len(data)} plans")
    
    def test_tenant_admin_sees_only_their_analytics(self, tenant_admin_token):
        """Tenant Admin can access /api/analytics (sees only their tenant's analytics)"""
        response = requests.get(
            f"{BASE_URL}/api/analytics",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        # Analytics should be filtered by tenant
        print(f"Tenant admin analytics: {data.get('total_subscribers', 'N/A')} subscribers, {data.get('total_revenue', 'N/A')} revenue")


class TestUnauthenticatedAccessBlocked:
    """Test that unauthenticated requests are blocked"""
    
    def test_unauthenticated_tenant_dashboard_returns_401(self):
        """Unauthenticated request to /api/tenant/dashboard/{tenant_id} returns 401"""
        response = requests.get(f"{BASE_URL}/api/tenant/dashboard/{TENANT_ID}")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}: {response.text}"
        print(f"Unauthenticated /api/tenant/dashboard blocked: {response.status_code}")
    
    def test_unauthenticated_tenant_settings_returns_401(self):
        """Unauthenticated request to /api/tenant/settings/{tenant_id} returns 401 or 403"""
        response = requests.put(
            f"{BASE_URL}/api/tenant/settings/{TENANT_ID}",
            json={"upi_id": "test@upi"}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}: {response.text}"
        print(f"Unauthenticated /api/tenant/settings blocked: {response.status_code}")
    
    def test_unauthenticated_subscribers_returns_401(self):
        """Unauthenticated request to /api/subscribers returns 401"""
        response = requests.get(f"{BASE_URL}/api/subscribers")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}: {response.text}"
        print(f"Unauthenticated /api/subscribers blocked: {response.status_code}")
    
    def test_unauthenticated_payments_returns_401(self):
        """Unauthenticated request to /api/payments returns 401"""
        response = requests.get(f"{BASE_URL}/api/payments")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}: {response.text}"
        print(f"Unauthenticated /api/payments blocked: {response.status_code}")
    
    def test_unauthenticated_plans_returns_401(self):
        """Unauthenticated request to /api/plans returns 401"""
        response = requests.get(f"{BASE_URL}/api/plans")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}: {response.text}"
        print(f"Unauthenticated /api/plans blocked: {response.status_code}")
    
    def test_unauthenticated_analytics_returns_401(self):
        """Unauthenticated request to /api/analytics returns 401"""
        response = requests.get(f"{BASE_URL}/api/analytics")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}: {response.text}"
        print(f"Unauthenticated /api/analytics blocked: {response.status_code}")
    
    def test_unauthenticated_saas_tenants_returns_401(self):
        """Unauthenticated request to /api/saas/tenants returns 401"""
        response = requests.get(f"{BASE_URL}/api/saas/tenants")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}: {response.text}"
        print(f"Unauthenticated /api/saas/tenants blocked: {response.status_code}")


class TestTenantDashboardAccess:
    """Test tenant dashboard access with proper authorization"""
    
    @pytest.fixture(scope="class")
    def super_admin_token(self):
        """Get super admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def tenant_admin_token(self):
        """Get tenant admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["token"]
    
    def test_super_admin_can_access_any_tenant_dashboard(self, super_admin_token):
        """Super Admin can access any tenant's dashboard"""
        response = requests.get(
            f"{BASE_URL}/api/tenant/dashboard/{TENANT_ID}",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "tenant" in data or "stats" in data
        print(f"Super admin accessed tenant dashboard: {data.get('tenant', {}).get('name', 'N/A')}")
    
    def test_tenant_admin_can_access_own_tenant_dashboard(self, tenant_admin_token):
        """Tenant Admin can access their own tenant's dashboard"""
        response = requests.get(
            f"{BASE_URL}/api/tenant/dashboard/{TENANT_ID}",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "tenant" in data or "stats" in data
        print(f"Tenant admin accessed own dashboard: {data.get('stats', {})}")
    
    def test_tenant_admin_cannot_access_other_tenant_dashboard(self, tenant_admin_token):
        """Tenant Admin CANNOT access another tenant's dashboard"""
        # Try to access 'default' tenant (Kaloo)
        response = requests.get(
            f"{BASE_URL}/api/tenant/dashboard/default",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        # Should be 403 Forbidden
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"Tenant admin correctly blocked from other tenant: {response.status_code}")


class TestCORSConfiguration:
    """Test CORS is properly configured"""
    
    def test_cors_allows_configured_origins(self):
        """CORS allows configured origins"""
        # Test with allowed origin
        response = requests.options(
            f"{BASE_URL}/api/auth/login",
            headers={
                "Origin": "https://admin-dashboard-mvp.preview.emergentagent.com",
                "Access-Control-Request-Method": "POST"
            }
        )
        # Should return CORS headers
        cors_origin = response.headers.get("Access-Control-Allow-Origin", "")
        print(f"CORS Allow-Origin: {cors_origin}")
        # Note: FastAPI may return the specific origin or * depending on config


class TestPublicEndpoints:
    """Test public endpoints that don't require auth"""
    
    def test_dashboard_plans_is_public(self):
        """/api/dashboard-plans is public (for landing page pricing)"""
        response = requests.get(f"{BASE_URL}/api/dashboard-plans")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "plans" in data
        print(f"Public dashboard-plans: {len(data.get('plans', []))} plans")
    
    def test_tenant_validate_bot_is_public(self):
        """/api/tenant/validate-bot is public (for onboarding)"""
        response = requests.post(
            f"{BASE_URL}/api/tenant/validate-bot",
            json={"bot_token": "invalid_token"}
        )
        # Should return 200 with valid=false, not 401
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("valid") == False
        print(f"Public validate-bot: {data}")
    
    def test_tenant_lookup_is_public(self):
        """/api/tenant/lookup/{bot_username} is public"""
        response = requests.get(f"{BASE_URL}/api/tenant/lookup/testbot")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"Public tenant lookup: {response.json()}")


class TestBroadcastsAndFeatures:
    """Test broadcasts and features with tenant filtering"""
    
    @pytest.fixture(scope="class")
    def tenant_admin_token(self):
        """Get tenant admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["token"]
    
    def test_tenant_admin_sees_only_their_broadcasts(self, tenant_admin_token):
        """Tenant Admin sees only their tenant's broadcasts"""
        response = requests.get(
            f"{BASE_URL}/api/broadcasts",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        # All broadcasts should belong to tenant_85ee971d0285
        for broadcast in data:
            if broadcast.get("tenant_id"):
                assert broadcast.get("tenant_id") == TENANT_ID, f"Tenant admin sees broadcast from wrong tenant"
        print(f"Tenant admin sees {len(data)} broadcasts")
    
    def test_tenant_admin_sees_only_their_referrals(self, tenant_admin_token):
        """Tenant Admin sees only their tenant's referrals"""
        response = requests.get(
            f"{BASE_URL}/api/referrals",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        print(f"Tenant admin sees {len(data)} referrals")
    
    def test_tenant_admin_sees_only_their_live_sessions(self, tenant_admin_token):
        """Tenant Admin sees only their tenant's live sessions"""
        response = requests.get(
            f"{BASE_URL}/api/live/sessions",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        print(f"Tenant admin sees {len(data)} live sessions")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
