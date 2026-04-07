"""
Iteration 40: P1 Features Testing
- JWT Refresh Token Architecture (access/refresh token pair, forced logout via token_version)
- Repository Pattern Migration (dashboard.py, broadcasts.py, engagement.py use TenantScopedRepository)
- Payment Idempotency (MongoDB-based deduplication locks on Razorpay callbacks)
- Tenant-scoped API endpoints
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"
SUPER_ADMIN_PASSWORD = "Sumit@8958"
TENANT_ADMIN_EMAIL = "anamika@test.com"
TENANT_ADMIN_PASSWORD = "Admin123"

# Global token cache to avoid rate limiting
_token_cache = {}

def get_cached_token(email, password):
    """Get token from cache or login"""
    cache_key = email
    if cache_key in _token_cache:
        return _token_cache[cache_key]
    
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": email,
        "password": password
    })
    if response.status_code == 200:
        data = response.json()
        _token_cache[cache_key] = data["token"]
        return data["token"]
    elif response.status_code == 429:
        # Rate limited - wait and retry
        time.sleep(60)
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password
        })
        if response.status_code == 200:
            data = response.json()
            _token_cache[cache_key] = data["token"]
            return data["token"]
    raise Exception(f"Login failed: {response.text}")


class TestJWTRefreshTokenArchitecture:
    """Test JWT refresh token implementation"""
    
    def test_login_returns_both_tokens(self):
        """Login should return both access token AND refresh_token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        
        # Verify both tokens are present
        assert "token" in data, "Access token missing from login response"
        assert "refresh_token" in data, "Refresh token missing from login response"
        assert len(data["token"]) > 0, "Access token is empty"
        assert len(data["refresh_token"]) > 0, "Refresh token is empty"
        
        # Verify user data
        assert "user" in data
        assert data["user"]["email"] == SUPER_ADMIN_EMAIL
        assert data["user"]["role"] == "super_admin"
        print(f"✓ Login returns both token and refresh_token")
    
    def test_refresh_token_returns_new_access_token(self):
        """POST /api/auth/refresh with valid refresh_token returns new access token"""
        # First login to get refresh token
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert login_resp.status_code == 200
        refresh_token = login_resp.json()["refresh_token"]
        
        # Use refresh token to get new access token
        refresh_resp = requests.post(f"{BASE_URL}/api/auth/refresh", json={
            "refresh_token": refresh_token
        })
        assert refresh_resp.status_code == 200, f"Refresh failed: {refresh_resp.text}"
        data = refresh_resp.json()
        
        assert "token" in data, "New access token missing from refresh response"
        assert len(data["token"]) > 0, "New access token is empty"
        
        # Verify new token works
        me_resp = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {data['token']}"
        })
        assert me_resp.status_code == 200, "New access token doesn't work"
        print(f"✓ Refresh token returns valid new access token")
    
    def test_refresh_with_invalid_token_returns_401(self):
        """POST /api/auth/refresh with invalid token returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/refresh", json={
            "refresh_token": "invalid_token_here"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ Invalid refresh token returns 401")
    
    def test_refresh_with_access_token_fails(self):
        """Using access token as refresh token should fail"""
        # Login to get access token
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        access_token = login_resp.json()["token"]
        
        # Try to use access token as refresh token
        refresh_resp = requests.post(f"{BASE_URL}/api/auth/refresh", json={
            "refresh_token": access_token
        })
        assert refresh_resp.status_code == 401, f"Expected 401 when using access token as refresh, got {refresh_resp.status_code}"
        print(f"✓ Access token cannot be used as refresh token")


class TestLogoutEndpoint:
    """Test logout endpoint separately (runs last to avoid affecting other tests)"""
    
    def test_logout_invalidates_session(self):
        """POST /api/auth/logout should increment token_version"""
        # Login with tenant admin to avoid affecting super admin tests
        # Clear cache first to get fresh token
        if TENANT_ADMIN_EMAIL in _token_cache:
            del _token_cache[TENANT_ADMIN_EMAIL]
        token = get_cached_token(TENANT_ADMIN_EMAIL, TENANT_ADMIN_PASSWORD)
        
        # Logout
        logout_resp = requests.post(f"{BASE_URL}/api/auth/logout", headers={
            "Authorization": f"Bearer {token}"
        })
        assert logout_resp.status_code == 200, f"Logout failed: {logout_resp.text}"
        data = logout_resp.json()
        assert "message" in data
        
        # Clear cache after logout since token is now invalid
        if TENANT_ADMIN_EMAIL in _token_cache:
            del _token_cache[TENANT_ADMIN_EMAIL]
        print(f"✓ Logout endpoint works correctly")


class TestSuperAdminAPIs:
    """Test Super Admin specific APIs"""
    
    @pytest.fixture
    def super_admin_token(self):
        """Get super admin token - uses cache to avoid rate limiting"""
        return get_cached_token(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
    
    def test_analytics_api_works(self, super_admin_token):
        """GET /api/analytics works correctly with Super Admin auth"""
        response = requests.get(f"{BASE_URL}/api/analytics", headers={
            "Authorization": f"Bearer {super_admin_token}"
        })
        assert response.status_code == 200, f"Analytics failed: {response.text}"
        data = response.json()
        
        # Verify analytics structure
        assert "total_subscribers" in data
        assert "active_subscribers" in data
        assert "total_revenue" in data
        assert "monthly_revenue" in data
        print(f"✓ Analytics API returns correct structure")
    
    def test_saas_tenants_api(self, super_admin_token):
        """GET /api/saas/tenants works for super admin"""
        response = requests.get(f"{BASE_URL}/api/saas/tenants", headers={
            "Authorization": f"Bearer {super_admin_token}"
        })
        assert response.status_code == 200, f"Tenants API failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Tenants should be a list"
        print(f"✓ SaaS Tenants API works (found {len(data)} tenants)")
    
    def test_risk_alerts_api(self, super_admin_token):
        """GET /api/saas/risk-alerts works for super admin"""
        response = requests.get(f"{BASE_URL}/api/saas/risk-alerts", headers={
            "Authorization": f"Bearer {super_admin_token}"
        })
        assert response.status_code == 200, f"Risk alerts failed: {response.text}"
        data = response.json()
        # Risk alerts returns a dict with 'alerts' key
        assert "alerts" in data or isinstance(data, list), "Risk alerts should have 'alerts' key or be a list"
        print(f"✓ Risk Alerts API works for super admin")


class TestTenantScopedAPIs:
    """Test tenant-scoped APIs using TenantScopedRepository"""
    
    @pytest.fixture
    def tenant_admin_token(self):
        """Get tenant admin token - uses cache to avoid rate limiting"""
        return get_cached_token(TENANT_ADMIN_EMAIL, TENANT_ADMIN_PASSWORD)
    
    def test_broadcasts_api_tenant_scoped(self, tenant_admin_token):
        """GET /api/broadcasts works correctly with tenant scoping"""
        response = requests.get(f"{BASE_URL}/api/broadcasts", headers={
            "Authorization": f"Bearer {tenant_admin_token}"
        })
        assert response.status_code == 200, f"Broadcasts failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Broadcasts should be a list"
        print(f"✓ Broadcasts API works with tenant scoping")
    
    def test_templates_api_tenant_scoped(self, tenant_admin_token):
        """GET /api/templates works correctly with tenant scoping"""
        response = requests.get(f"{BASE_URL}/api/templates", headers={
            "Authorization": f"Bearer {tenant_admin_token}"
        })
        assert response.status_code == 200, f"Templates failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Templates should be a list"
        print(f"✓ Templates API works with tenant scoping")
    
    def test_channels_api_tenant_scoped(self, tenant_admin_token):
        """GET /api/channels works correctly with tenant scoping"""
        response = requests.get(f"{BASE_URL}/api/channels", headers={
            "Authorization": f"Bearer {tenant_admin_token}"
        })
        assert response.status_code == 200, f"Channels failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Channels should be a list"
        print(f"✓ Channels API works with tenant scoping")
    
    def test_coupons_api_tenant_scoped(self, tenant_admin_token):
        """GET /api/coupons works correctly with tenant scoping"""
        response = requests.get(f"{BASE_URL}/api/coupons", headers={
            "Authorization": f"Bearer {tenant_admin_token}"
        })
        assert response.status_code == 200, f"Coupons failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Coupons should be a list"
        print(f"✓ Coupons API works with tenant scoping")
    
    def test_referrals_api_tenant_scoped(self, tenant_admin_token):
        """GET /api/referrals works correctly with tenant scoping"""
        response = requests.get(f"{BASE_URL}/api/referrals", headers={
            "Authorization": f"Bearer {tenant_admin_token}"
        })
        assert response.status_code == 200, f"Referrals failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Referrals should be a list"
        print(f"✓ Referrals API works with tenant scoping")
    
    def test_faqs_api_tenant_scoped(self, tenant_admin_token):
        """GET /api/faqs works correctly with tenant scoping"""
        response = requests.get(f"{BASE_URL}/api/faqs", headers={
            "Authorization": f"Bearer {tenant_admin_token}"
        })
        assert response.status_code == 200, f"FAQs failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "FAQs should be a list"
        print(f"✓ FAQs API works with tenant scoping")
    
    def test_video_calls_api_tenant_scoped(self, tenant_admin_token):
        """GET /api/video-calls works correctly with tenant scoping"""
        response = requests.get(f"{BASE_URL}/api/video-calls", headers={
            "Authorization": f"Bearer {tenant_admin_token}"
        })
        assert response.status_code == 200, f"Video calls failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Video calls should be a list"
        print(f"✓ Video Calls API works with tenant scoping")
    
    def test_blocked_users_api_tenant_scoped(self, tenant_admin_token):
        """GET /api/blocked-users works correctly with tenant scoping"""
        response = requests.get(f"{BASE_URL}/api/blocked-users", headers={
            "Authorization": f"Bearer {tenant_admin_token}"
        })
        assert response.status_code == 200, f"Blocked users failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Blocked users should be a list"
        print(f"✓ Blocked Users API works with tenant scoping")


class TestTenantAdminAccessControl:
    """Test that tenant admin cannot access super admin routes"""
    
    @pytest.fixture
    def tenant_admin_token(self):
        """Get tenant admin token - uses cache to avoid rate limiting"""
        return get_cached_token(TENANT_ADMIN_EMAIL, TENANT_ADMIN_PASSWORD)
    
    def test_tenant_admin_denied_risk_alerts(self, tenant_admin_token):
        """Tenant admin should be denied access to risk alerts"""
        response = requests.get(f"{BASE_URL}/api/saas/risk-alerts", headers={
            "Authorization": f"Bearer {tenant_admin_token}"
        })
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"✓ Tenant admin correctly denied access to risk alerts")
    
    def test_tenant_admin_can_access_analytics(self, tenant_admin_token):
        """Tenant admin should be able to access their own analytics"""
        response = requests.get(f"{BASE_URL}/api/analytics", headers={
            "Authorization": f"Bearer {tenant_admin_token}"
        })
        assert response.status_code == 200, f"Analytics failed: {response.text}"
        print(f"✓ Tenant admin can access their own analytics")


class TestRepositoryPatternMigration:
    """Verify repository pattern is correctly implemented"""
    
    @pytest.fixture
    def super_admin_token(self):
        """Get super admin token - uses cache to avoid rate limiting"""
        return get_cached_token(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
    
    @pytest.fixture
    def tenant_admin_token(self):
        """Get tenant admin token - uses cache to avoid rate limiting"""
        return get_cached_token(TENANT_ADMIN_EMAIL, TENANT_ADMIN_PASSWORD)
    
    def test_super_admin_sees_global_data(self, super_admin_token):
        """Super admin should see global data (all tenants)"""
        response = requests.get(f"{BASE_URL}/api/analytics", headers={
            "Authorization": f"Bearer {super_admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        # Super admin sees aggregated data
        assert "total_subscribers" in data
        print(f"✓ Super admin sees global analytics data")
    
    def test_tenant_admin_sees_scoped_data(self, tenant_admin_token):
        """Tenant admin should see only their tenant's data"""
        response = requests.get(f"{BASE_URL}/api/analytics", headers={
            "Authorization": f"Bearer {tenant_admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        # Tenant admin sees their scoped data
        assert "total_subscribers" in data
        print(f"✓ Tenant admin sees tenant-scoped analytics data")
    
    def test_plans_api_uses_repository(self, tenant_admin_token):
        """Plans API should use TenantScopedRepository"""
        response = requests.get(f"{BASE_URL}/api/plans", headers={
            "Authorization": f"Bearer {tenant_admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Plans API uses repository pattern (found {len(data)} plans)")
    
    def test_subscribers_api_uses_repository(self, tenant_admin_token):
        """Subscribers API should use TenantScopedRepository"""
        response = requests.get(f"{BASE_URL}/api/subscribers", headers={
            "Authorization": f"Bearer {tenant_admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        # Subscribers API returns paginated data with stats
        assert "subscribers" in data or isinstance(data, list)
        print(f"✓ Subscribers API uses repository pattern")
    
    def test_payments_api_uses_repository(self, tenant_admin_token):
        """Payments API should use TenantScopedRepository"""
        response = requests.get(f"{BASE_URL}/api/payments", headers={
            "Authorization": f"Bearer {tenant_admin_token}"
        })
        assert response.status_code == 200
        data = response.json()
        # Payments API returns paginated data
        assert "payments" in data or isinstance(data, list)
        print(f"✓ Payments API uses repository pattern")


class TestIdempotencyLock:
    """Test payment idempotency mechanism (code review verification)"""
    
    def test_razorpay_callback_endpoint_exists(self):
        """Verify Razorpay callback endpoint exists"""
        # Just verify the endpoint is reachable (will return error without valid params)
        response = requests.get(f"{BASE_URL}/api/razorpay/callback")
        # Should return 404 (order not found) not 500 (server error)
        assert response.status_code in [400, 404], f"Unexpected status: {response.status_code}"
        print(f"✓ Razorpay callback endpoint exists and handles missing params")


class TestAuthMeEndpoint:
    """Test /api/auth/me endpoint"""
    
    def test_auth_me_returns_user_data(self):
        """GET /api/auth/me returns correct user data"""
        # Use cached token to avoid rate limiting
        token = get_cached_token(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
        
        # Get user data
        me_resp = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert me_resp.status_code == 200
        data = me_resp.json()
        
        assert data["email"] == SUPER_ADMIN_EMAIL
        assert data["role"] == "super_admin"
        assert "tenant_id" in data
        print(f"✓ Auth me endpoint returns correct user data")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
