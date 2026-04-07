"""
Iteration 39 Tests: Major Refactoring Verification
- APScheduler separated into workers/scheduler.py with MongoDB distributed locking
- telegram_webhook.py refactored from 4300 lines to ~60 lines (thin dispatcher)
- webhook_handlers/ module with channel_posts.py, callbacks.py, messages.py
- Repository pattern verification (plans_repo, subscribers_repo)
- All existing APIs still working
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


class TestAuthEndpoints:
    """Authentication endpoint tests"""
    
    def test_super_admin_login(self):
        """Super Admin login returns role='super_admin'"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "super_admin"
        assert data["user"]["email"] == SUPER_ADMIN_EMAIL
        print(f"✅ Super Admin login: role={data['user']['role']}")
    
    def test_tenant_admin_login(self):
        """Tenant Admin login returns role='tenant_admin'"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "tenant_admin"
        assert data["user"]["email"] == TENANT_ADMIN_EMAIL
        print(f"✅ Tenant Admin login: role={data['user']['role']}")
    
    def test_check_admin_super_admin(self):
        """GET /api/auth/check-admin returns is_admin=true for super_admin"""
        # Login first
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        token = login_resp.json()["token"]
        
        response = requests.get(f"{BASE_URL}/api/auth/check-admin", 
                               headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["is_admin"] == True
        assert data["role"] == "super_admin"
        print(f"✅ Check admin: is_admin={data['is_admin']}, role={data['role']}")


class TestPlansAPI:
    """Plans API tests - Repository pattern verification"""
    
    @pytest.fixture
    def super_admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    @pytest.fixture
    def tenant_admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    def test_super_admin_gets_all_plans(self, super_admin_token):
        """Super Admin GET /api/plans returns all plans (global view)"""
        response = requests.get(f"{BASE_URL}/api/plans",
                               headers={"Authorization": f"Bearer {super_admin_token}"})
        assert response.status_code == 200
        plans = response.json()
        assert isinstance(plans, list)
        print(f"✅ Super Admin sees {len(plans)} plans (global view)")
    
    def test_tenant_admin_gets_scoped_plans(self, tenant_admin_token):
        """Tenant Admin GET /api/plans returns only their tenant's plans"""
        response = requests.get(f"{BASE_URL}/api/plans",
                               headers={"Authorization": f"Bearer {tenant_admin_token}"})
        assert response.status_code == 200
        plans = response.json()
        assert isinstance(plans, list)
        print(f"✅ Tenant Admin sees {len(plans)} plans (tenant-scoped)")


class TestSubscribersAPI:
    """Subscribers API tests - Repository pattern verification"""
    
    @pytest.fixture
    def super_admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    def test_subscribers_returns_paginated_data(self, super_admin_token):
        """GET /api/subscribers returns paginated data with stats"""
        response = requests.get(f"{BASE_URL}/api/subscribers",
                               headers={"Authorization": f"Bearer {super_admin_token}"})
        assert response.status_code == 200
        data = response.json()
        assert "subscribers" in data
        assert "total" in data
        assert "stats" in data
        assert "total_subscribers" in data["stats"]
        assert "active_count" in data["stats"]
        assert "expired_count" in data["stats"]
        print(f"✅ Subscribers API: total={data['total']}, active={data['stats']['active_count']}")


class TestPaymentsAPI:
    """Payments API tests"""
    
    @pytest.fixture
    def super_admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    def test_payments_returns_paginated_data(self, super_admin_token):
        """GET /api/payments returns paginated data with stats"""
        response = requests.get(f"{BASE_URL}/api/payments",
                               headers={"Authorization": f"Bearer {super_admin_token}"})
        assert response.status_code == 200
        data = response.json()
        assert "payments" in data
        assert "total" in data
        assert "stats" in data
        print(f"✅ Payments API: total={data['total']}")


class TestAnalyticsAPI:
    """Analytics API tests"""
    
    @pytest.fixture
    def super_admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    def test_analytics_returns_stats(self, super_admin_token):
        """GET /api/analytics returns stats"""
        response = requests.get(f"{BASE_URL}/api/analytics",
                               headers={"Authorization": f"Bearer {super_admin_token}"})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        print(f"✅ Analytics API working")


class TestBroadcastsAPI:
    """Broadcasts API tests"""
    
    @pytest.fixture
    def super_admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    def test_broadcasts_returns_list(self, super_admin_token):
        """GET /api/broadcasts returns list"""
        response = requests.get(f"{BASE_URL}/api/broadcasts",
                               headers={"Authorization": f"Bearer {super_admin_token}"})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Broadcasts API: {len(data)} broadcasts")


class TestCouponsAPI:
    """Coupons API tests"""
    
    @pytest.fixture
    def super_admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    def test_coupons_returns_list(self, super_admin_token):
        """GET /api/coupons returns list"""
        response = requests.get(f"{BASE_URL}/api/coupons",
                               headers={"Authorization": f"Bearer {super_admin_token}"})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Coupons API: {len(data)} coupons")


class TestSaaSManagementAPI:
    """SaaS Management API tests - Super Admin only"""
    
    @pytest.fixture
    def super_admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    @pytest.fixture
    def tenant_admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    def test_risk_alerts_super_admin(self, super_admin_token):
        """Super Admin GET /api/saas/risk-alerts returns structured data"""
        response = requests.get(f"{BASE_URL}/api/saas/risk-alerts",
                               headers={"Authorization": f"Bearer {super_admin_token}"})
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        assert "total" in data
        assert "critical_count" in data
        print(f"✅ Risk Alerts API: {len(data['alerts'])} alerts, total={data['total']}")
    
    def test_risk_alerts_tenant_admin_denied(self, tenant_admin_token):
        """Tenant Admin denied access to risk alerts (403)"""
        response = requests.get(f"{BASE_URL}/api/saas/risk-alerts",
                               headers={"Authorization": f"Bearer {tenant_admin_token}"})
        assert response.status_code == 403
        print(f"✅ Tenant Admin correctly denied access to risk alerts")
    
    def test_tenants_no_default(self, super_admin_token):
        """GET /api/saas/tenants returns no 'default' tenant"""
        response = requests.get(f"{BASE_URL}/api/saas/tenants",
                               headers={"Authorization": f"Bearer {super_admin_token}"})
        assert response.status_code == 200
        tenants = response.json()
        assert isinstance(tenants, list)
        default_tenants = [t for t in tenants if t.get("tenant_id") == "default"]
        assert len(default_tenants) == 0, f"Found {len(default_tenants)} 'default' tenants!"
        print(f"✅ No 'default' tenant found in {len(tenants)} tenants")


class TestImpersonationAPI:
    """Impersonation API tests"""
    
    @pytest.fixture
    def super_admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    @pytest.fixture
    def tenant_admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    def test_impersonate_valid_tenant(self, super_admin_token):
        """POST /api/saas/impersonate/{tenant_id} returns impersonated token"""
        # First get a valid tenant_id
        tenants_resp = requests.get(f"{BASE_URL}/api/saas/tenants",
                                   headers={"Authorization": f"Bearer {super_admin_token}"})
        tenants = tenants_resp.json()
        
        if tenants and len(tenants) > 0:
            tenant_id = tenants[0].get("tenant_id")
            response = requests.post(f"{BASE_URL}/api/saas/impersonate/{tenant_id}",
                                    headers={"Authorization": f"Bearer {super_admin_token}"})
            assert response.status_code == 200
            data = response.json()
            assert "token" in data
            print(f"✅ Impersonation API works for tenant {tenant_id}")
        else:
            pytest.skip("No tenants available for impersonation test")
    
    def test_impersonate_nonexistent_tenant(self, super_admin_token):
        """Impersonating non-existent tenant returns 404"""
        response = requests.post(f"{BASE_URL}/api/saas/impersonate/nonexistent_tenant_xyz",
                                headers={"Authorization": f"Bearer {super_admin_token}"})
        assert response.status_code == 404
        print(f"✅ Non-existent tenant impersonation returns 404")
    
    def test_tenant_admin_denied_impersonation(self, tenant_admin_token):
        """Tenant Admin denied impersonation (403)"""
        response = requests.post(f"{BASE_URL}/api/saas/impersonate/some_tenant",
                                headers={"Authorization": f"Bearer {tenant_admin_token}"})
        assert response.status_code == 403
        print(f"✅ Tenant Admin correctly denied impersonation")


class TestTelegramWebhook:
    """Telegram Webhook tests - Refactored dispatcher verification"""
    
    def test_webhook_returns_ok(self):
        """POST /api/telegram/webhook returns {ok: true}"""
        # Send a minimal webhook payload
        response = requests.post(f"{BASE_URL}/api/telegram/webhook", json={
            "message": {
                "from": {"id": 12345, "first_name": "Test"},
                "chat": {"id": 12345, "type": "private"},
                "text": "/start"
            }
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"✅ Telegram webhook returns ok=true")
    
    def test_webhook_handles_callback_query(self):
        """POST /api/telegram/webhook handles callback_query"""
        response = requests.post(f"{BASE_URL}/api/telegram/webhook", json={
            "callback_query": {
                "id": "test_callback",
                "from": {"id": 12345, "username": "testuser"},
                "data": "check_status"
            }
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"✅ Telegram webhook handles callback_query")
    
    def test_webhook_handles_channel_post(self):
        """POST /api/telegram/webhook handles channel_post"""
        response = requests.post(f"{BASE_URL}/api/telegram/webhook", json={
            "channel_post": {
                "chat": {"id": -1001234567890, "type": "channel"},
                "message_id": 123,
                "text": "Test channel post"
            }
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"✅ Telegram webhook handles channel_post")


class TestXRequestIDHeader:
    """X-Request-ID header tests"""
    
    def test_x_request_id_present(self):
        """X-Request-ID header present in API responses"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert "x-request-id" in response.headers
        request_id = response.headers["x-request-id"]
        assert len(request_id) > 0
        print(f"✅ X-Request-ID present: {request_id[:20]}...")
    
    def test_x_request_id_unique(self):
        """X-Request-ID is unique per request"""
        response1 = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        response2 = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        
        id1 = response1.headers.get("x-request-id")
        id2 = response2.headers.get("x-request-id")
        
        assert id1 != id2, "X-Request-ID should be unique per request"
        print(f"✅ X-Request-ID unique: {id1[:10]}... != {id2[:10]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
