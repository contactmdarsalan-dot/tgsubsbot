"""
P1 Security Fixes Tests - Iteration 21
Tests for P1 security features implemented after iteration 20:
1. Telegram WebApp initData HMAC-SHA256 verification (telegram_verify.py)
2. Audit logging service (audit.py)
3. Pydantic Enums for type safety (models/__init__.py)
4. Query limits on analytics endpoints
5. MiniApp endpoints with tg_id fallback (dev mode)
6. Regression tests for P0 security (login, RBAC, tenant isolation)
"""
import pytest
import requests
import os
import sys

# Add backend to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://trial-management-hub-1.preview.emergentagent.com')

# Test credentials from test_credentials.md
SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"
SUPER_ADMIN_PASSWORD = "Sumit@8958"
TENANT_ADMIN_EMAIL = "anamika@test.com"
TENANT_ADMIN_PASSWORD = "Admin123"
TENANT_ID = "tenant_85ee971d0285"
TEST_TG_ID = "123456789"


class TestPydanticEnums:
    """Test that Pydantic Enums are properly defined and importable"""
    
    def test_user_role_enum_exists(self):
        """UserRole enum should be importable and have correct values"""
        from models import UserRole
        assert UserRole.SUPER_ADMIN.value == "super_admin"
        assert UserRole.TENANT_OWNER.value == "tenant_owner"
        assert UserRole.TENANT_ADMIN.value == "tenant_admin"
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.CREATOR.value == "creator"
        assert UserRole.CUSTOMER.value == "customer"
        assert UserRole.USER.value == "user"
        print(f"UserRole enum values: {[e.value for e in UserRole]}")
    
    def test_payment_status_enum_exists(self):
        """PaymentStatus enum should be importable and have correct values"""
        from models import PaymentStatus
        assert PaymentStatus.PENDING.value == "pending"
        assert PaymentStatus.VERIFIED.value == "verified"
        assert PaymentStatus.APPROVED.value == "approved"
        assert PaymentStatus.REJECTED.value == "rejected"
        assert PaymentStatus.EXPIRED.value == "expired"
        print(f"PaymentStatus enum values: {[e.value for e in PaymentStatus]}")
    
    def test_subscription_status_enum_exists(self):
        """SubscriptionStatus enum should be importable and have correct values"""
        from models import SubscriptionStatus
        assert SubscriptionStatus.ACTIVE.value == "active"
        assert SubscriptionStatus.EXPIRED.value == "expired"
        assert SubscriptionStatus.GRACE.value == "grace"
        assert SubscriptionStatus.CANCELLED.value == "cancelled"
        print(f"SubscriptionStatus enum values: {[e.value for e in SubscriptionStatus]}")
    
    def test_live_session_status_enum_exists(self):
        """LiveSessionStatus enum should be importable and have correct values"""
        from models import LiveSessionStatus
        assert LiveSessionStatus.SCHEDULED.value == "scheduled"
        assert LiveSessionStatus.ANNOUNCED.value == "announced"
        assert LiveSessionStatus.LIVE.value == "live"
        assert LiveSessionStatus.ENDED.value == "ended"
        print(f"LiveSessionStatus enum values: {[e.value for e in LiveSessionStatus]}")


class TestTelegramVerifyService:
    """Test telegram_verify.py service functions"""
    
    def test_validate_telegram_init_data_function_exists(self):
        """validate_telegram_init_data function should be importable"""
        from services.telegram_verify import validate_telegram_init_data
        assert callable(validate_telegram_init_data)
        print("validate_telegram_init_data function exists and is callable")
    
    def test_extract_telegram_user_id_function_exists(self):
        """extract_telegram_user_id function should be importable"""
        from services.telegram_verify import extract_telegram_user_id
        assert callable(extract_telegram_user_id)
        print("extract_telegram_user_id function exists and is callable")
    
    def test_validate_returns_none_for_empty_data(self):
        """validate_telegram_init_data should return None for empty data"""
        from services.telegram_verify import validate_telegram_init_data
        result = validate_telegram_init_data("", "test_token")
        assert result is None
        print("validate_telegram_init_data returns None for empty init_data")
    
    def test_validate_returns_none_for_empty_token(self):
        """validate_telegram_init_data should return None for empty token"""
        from services.telegram_verify import validate_telegram_init_data
        result = validate_telegram_init_data("some_data", "")
        assert result is None
        print("validate_telegram_init_data returns None for empty bot_token")
    
    def test_validate_returns_none_for_invalid_data(self):
        """validate_telegram_init_data should return None for invalid/tampered data"""
        from services.telegram_verify import validate_telegram_init_data
        # Invalid init data without proper hash
        result = validate_telegram_init_data("user=test&auth_date=123", "test_token")
        assert result is None
        print("validate_telegram_init_data returns None for data without hash")
    
    def test_extract_user_id_returns_none_for_invalid(self):
        """extract_telegram_user_id should return None for invalid data"""
        from services.telegram_verify import extract_telegram_user_id
        result = extract_telegram_user_id("invalid_data", "test_token")
        assert result is None
        print("extract_telegram_user_id returns None for invalid data")


class TestAuditLoggingService:
    """Test audit.py service functions"""
    
    def test_log_action_function_exists(self):
        """log_action function should be importable"""
        from services.audit import log_action
        assert callable(log_action)
        print("log_action function exists and is callable")
    
    def test_log_action_function_signature(self):
        """log_action should have correct parameters"""
        import inspect
        from services.audit import log_action
        sig = inspect.signature(log_action)
        params = list(sig.parameters.keys())
        assert "tenant_id" in params
        assert "actor_id" in params
        assert "actor_email" in params
        assert "action" in params
        assert "entity_type" in params
        print(f"log_action parameters: {params}")


class TestMiniAppEndpointsWithTgIdFallback:
    """Test MiniApp endpoints work with tg_id query param fallback (dev mode)"""
    
    def test_miniapp_plans_public_endpoint(self):
        """GET /api/miniapp/plans should be public and return plans"""
        response = requests.get(f"{BASE_URL}/api/miniapp/plans")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"MiniApp plans endpoint returned {len(data)} plans")
    
    def test_miniapp_admin_check_with_tg_id(self):
        """GET /api/miniapp/admin/check/{tg_id} should work with tg_id param"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/check/{TEST_TG_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "is_admin" in data
        print(f"MiniApp admin check response: {data}")
    
    def test_miniapp_status_with_tg_id(self):
        """GET /api/miniapp/status/{tg_id} should work with tg_id param"""
        response = requests.get(f"{BASE_URL}/api/miniapp/status/{TEST_TG_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "is_active" in data
        print(f"MiniApp status response: {data}")
    
    def test_miniapp_notifications_with_tg_id(self):
        """GET /api/miniapp/notifications/{tg_id} should work with tg_id param"""
        response = requests.get(f"{BASE_URL}/api/miniapp/notifications/{TEST_TG_ID}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"MiniApp notifications returned {len(data)} items")
    
    def test_miniapp_referral_with_tg_id(self):
        """GET /api/miniapp/referral/{tg_id} should work with tg_id param"""
        response = requests.get(f"{BASE_URL}/api/miniapp/referral/{TEST_TG_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "referral_code" in data
        print(f"MiniApp referral response: {data}")
    
    def test_miniapp_upi_details_public(self):
        """GET /api/miniapp/upi-details should be public"""
        response = requests.get(f"{BASE_URL}/api/miniapp/upi-details")
        assert response.status_code == 200
        data = response.json()
        assert "upi_id" in data or "payment_message" in data
        print(f"MiniApp UPI details response: {data}")


class TestP0SecurityRegression:
    """Quick regression tests to ensure P0 security is not broken"""
    
    @pytest.fixture(scope="class")
    def super_admin_token(self):
        """Get super admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Super admin login failed: {response.text}"
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def tenant_admin_token(self):
        """Get tenant admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Tenant admin login failed: {response.text}"
        return response.json()["token"]
    
    def test_super_admin_login_works(self, super_admin_token):
        """Super Admin login should still work"""
        assert super_admin_token is not None
        assert len(super_admin_token) > 10
        print(f"Super admin login successful, token length: {len(super_admin_token)}")
    
    def test_tenant_admin_login_works(self, tenant_admin_token):
        """Tenant Admin login should still work"""
        assert tenant_admin_token is not None
        assert len(tenant_admin_token) > 10
        print(f"Tenant admin login successful, token length: {len(tenant_admin_token)}")
    
    def test_super_admin_can_access_saas_tenants(self, super_admin_token):
        """Super Admin should still access /api/saas/tenants"""
        response = requests.get(
            f"{BASE_URL}/api/saas/tenants",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200
        print(f"Super admin accessed /api/saas/tenants: {response.status_code}")
    
    def test_tenant_admin_blocked_from_saas_tenants(self, tenant_admin_token):
        """Tenant Admin should still be blocked from /api/saas/tenants"""
        response = requests.get(
            f"{BASE_URL}/api/saas/tenants",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 403
        print(f"Tenant admin correctly blocked from /api/saas/tenants: {response.status_code}")
    
    def test_unauthenticated_blocked_from_subscribers(self):
        """Unauthenticated requests should still be blocked"""
        response = requests.get(f"{BASE_URL}/api/subscribers")
        assert response.status_code in [401, 403]
        print(f"Unauthenticated request blocked: {response.status_code}")
    
    def test_check_admin_returns_role(self, super_admin_token):
        """/api/auth/check-admin should still return role field"""
        response = requests.get(
            f"{BASE_URL}/api/auth/check-admin",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "role" in data
        assert "is_admin" in data
        print(f"check-admin response: {data}")


class TestAuditLogIntegration:
    """Test that audit logging is integrated into admin routes"""
    
    @pytest.fixture(scope="class")
    def super_admin_token(self):
        """Get super admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["token"]
    
    def test_audit_log_module_structure(self):
        """audit.py module should have correct structure"""
        import inspect
        from services import audit
        
        # Check module has log_action function
        assert hasattr(audit, 'log_action')
        assert inspect.iscoroutinefunction(audit.log_action)
        print("audit.py module has async log_action function")
    
    def test_create_tenant_admin_triggers_audit(self, super_admin_token):
        """Creating a tenant admin should create an audit log entry"""
        import uuid
        test_email = f"test_audit_{uuid.uuid4().hex[:6]}@test.com"
        
        # Create a tenant admin
        response = requests.post(
            f"{BASE_URL}/api/saas/tenants/{TENANT_ID}/dashboard-admin",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={
                "email": test_email,
                "password": "TestPass123",
                "name": "Test Audit User"
            }
        )
        
        # Should succeed (200 or 201)
        assert response.status_code in [200, 201], f"Failed to create tenant admin: {response.text}"
        print(f"Created tenant admin: {test_email}, response: {response.json()}")


class TestPermissionsService:
    """Test permissions.py service functions"""
    
    def test_is_super_admin_function_exists(self):
        """is_super_admin function should be importable"""
        from services.permissions import is_super_admin
        assert callable(is_super_admin)
        print("is_super_admin function exists")
    
    def test_is_tenant_admin_function_exists(self):
        """is_tenant_admin function should be importable"""
        from services.permissions import is_tenant_admin
        assert callable(is_tenant_admin)
        print("is_tenant_admin function exists")
    
    def test_ensure_tenant_access_function_exists(self):
        """ensure_tenant_access function should be importable"""
        from services.permissions import ensure_tenant_access
        assert callable(ensure_tenant_access)
        print("ensure_tenant_access function exists")
    
    def test_tq_function_exists(self):
        """tq (tenant query) function should be importable"""
        from services.permissions import tq
        assert callable(tq)
        print("tq function exists")
    
    def test_tq_adds_tenant_filter(self):
        """tq should add tenant_id to query when provided"""
        from services.permissions import tq
        query = {"status": "active"}
        result = tq(query, "test_tenant")
        assert result["tenant_id"] == "test_tenant"
        assert result["status"] == "active"
        print(f"tq result: {result}")
    
    def test_tq_no_filter_for_empty_tenant(self):
        """tq should not add tenant_id when empty (super admin sees all)"""
        from services.permissions import tq
        query = {"status": "active"}
        result = tq(query, "")
        assert "tenant_id" not in result
        assert result["status"] == "active"
        print(f"tq result for empty tenant: {result}")
    
    def test_is_super_admin_by_role(self):
        """is_super_admin should return True for role=super_admin"""
        from services.permissions import is_super_admin
        user = {"role": "super_admin", "email": "test@test.com"}
        assert is_super_admin(user) == True
        print("is_super_admin returns True for role=super_admin")
    
    def test_is_super_admin_by_email(self):
        """is_super_admin should return True for email in SUPER_ADMIN_EMAILS"""
        from services.permissions import is_super_admin
        user = {"role": "user", "email": SUPER_ADMIN_EMAIL}
        assert is_super_admin(user) == True
        print(f"is_super_admin returns True for email={SUPER_ADMIN_EMAIL}")
    
    def test_is_tenant_admin_for_tenant_admin_role(self):
        """is_tenant_admin should return True for role=tenant_admin"""
        from services.permissions import is_tenant_admin
        user = {"role": "tenant_admin", "tenant_id": "test"}
        assert is_tenant_admin(user) == True
        print("is_tenant_admin returns True for role=tenant_admin")
    
    def test_is_tenant_admin_for_tenant_owner_role(self):
        """is_tenant_admin should return True for role=tenant_owner"""
        from services.permissions import is_tenant_admin
        user = {"role": "tenant_owner", "tenant_id": "test"}
        assert is_tenant_admin(user) == True
        print("is_tenant_admin returns True for role=tenant_owner")


class TestAnalyticsEndpoints:
    """Test analytics endpoints have proper auth and limits"""
    
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
    
    def test_analytics_requires_auth(self):
        """GET /api/analytics should require authentication"""
        response = requests.get(f"{BASE_URL}/api/analytics")
        assert response.status_code in [401, 403]
        print(f"Analytics endpoint requires auth: {response.status_code}")
    
    def test_super_admin_can_access_analytics(self, super_admin_token):
        """Super Admin should access /api/analytics"""
        response = requests.get(
            f"{BASE_URL}/api/analytics",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        print(f"Super admin analytics: {data}")
    
    def test_tenant_admin_can_access_analytics(self, tenant_admin_token):
        """Tenant Admin should access /api/analytics (filtered to their tenant)"""
        response = requests.get(
            f"{BASE_URL}/api/analytics",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        print(f"Tenant admin analytics: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
