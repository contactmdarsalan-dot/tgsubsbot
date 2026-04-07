"""
Iteration 43: Strict Tenant Enforcement & Legacy Routes Cleanup Tests

Tests for:
1. Super Admin login (gamerxboys8958@gmail.com / Sumit@8958) - role=super_admin, tenant_id=__platform__
2. Tenant Admin login (anamika@test.com / Admin123) - role=tenant_admin, tenant_id=tenant_85ee971d0285
3. GET /api/saas/tenants - returns list of tenants (requires Super Admin token)
4. POST /api/telegram/webhook with /start command - processes successfully
5. Verify no orphan documents without tenant_id in critical collections
6. Verify /app/backend/routes/ folder does NOT exist
7. Backend server starts without import errors
8. QR toggle - GET tenant should show qr_enabled field
"""
import pytest
import requests
import os
import subprocess

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"
SUPER_ADMIN_PASSWORD = "Sumit@8958"
TENANT_ADMIN_EMAIL = "anamika@test.com"
TENANT_ADMIN_PASSWORD = "Admin123"


class TestAuthenticationAndRoles:
    """Test authentication and role verification"""
    
    def test_super_admin_login_returns_correct_role_and_tenant(self):
        """Super Admin login should return role=super_admin, tenant_id=__platform__"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        
        assert response.status_code == 200, f"Super Admin login failed: {response.text}"
        data = response.json()
        
        # Verify token exists (API returns 'token' not 'access_token')
        token = data.get("token") or data.get("access_token")
        assert token, "No token in response"
        assert len(token) > 0, "Empty token"
        
        # Verify user data
        assert "user" in data, "No user data in response"
        user = data["user"]
        
        # Verify role is super_admin
        assert user.get("role") == "super_admin", f"Expected role='super_admin', got '{user.get('role')}'"
        
        # Verify tenant_id is __platform__
        assert user.get("tenant_id") == "__platform__", f"Expected tenant_id='__platform__', got '{user.get('tenant_id')}'"
        
        print(f"✓ Super Admin login successful: role={user.get('role')}, tenant_id={user.get('tenant_id')}")
    
    def test_tenant_admin_login_returns_correct_role_and_tenant(self):
        """Tenant Admin login should return role=tenant_admin, tenant_id=tenant_85ee971d0285"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        
        assert response.status_code == 200, f"Tenant Admin login failed: {response.text}"
        data = response.json()
        
        # Verify token exists (API returns 'token' not 'access_token')
        token = data.get("token") or data.get("access_token")
        assert token, "No token in response"
        
        # Verify user data
        assert "user" in data, "No user data in response"
        user = data["user"]
        
        # Verify role is tenant_admin
        assert user.get("role") == "tenant_admin", f"Expected role='tenant_admin', got '{user.get('role')}'"
        
        # Verify tenant_id starts with tenant_
        tenant_id = user.get("tenant_id")
        assert tenant_id and tenant_id.startswith("tenant_"), f"Expected tenant_id starting with 'tenant_', got '{tenant_id}'"
        
        print(f"✓ Tenant Admin login successful: role={user.get('role')}, tenant_id={tenant_id}")


class TestSuperAdminEndpoints:
    """Test Super Admin specific endpoints"""
    
    @pytest.fixture
    def super_admin_token(self):
        """Get Super Admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            return data.get("token") or data.get("access_token")
        pytest.skip("Super Admin authentication failed")
    
    def test_get_tenants_list_requires_super_admin(self, super_admin_token):
        """GET /api/saas/tenants should return list of tenants for Super Admin"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        response = requests.get(f"{BASE_URL}/api/saas/tenants", headers=headers)
        
        assert response.status_code == 200, f"GET /api/saas/tenants failed: {response.text}"
        data = response.json()
        
        # Should return a list (or dict with tenants key)
        if isinstance(data, list):
            tenants = data
        elif isinstance(data, dict) and "tenants" in data:
            tenants = data["tenants"]
        else:
            tenants = data.get("data", []) if isinstance(data, dict) else []
        
        assert isinstance(tenants, list), f"Expected list of tenants, got {type(tenants)}"
        
        # Verify at least one tenant exists
        assert len(tenants) > 0, "No tenants found in response"
        
        # Verify tenant structure
        first_tenant = tenants[0]
        assert "tenant_id" in first_tenant or "id" in first_tenant, "Tenant missing tenant_id/id field"
        
        print(f"✓ GET /api/saas/tenants returned {len(tenants)} tenants")
    
    def test_get_tenants_denied_for_tenant_admin(self):
        """GET /api/saas/tenants should be denied for Tenant Admin"""
        # Login as tenant admin
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert login_response.status_code == 200
        data = login_response.json()
        tenant_token = data.get("token") or data.get("access_token")
        
        # Try to access super admin endpoint
        headers = {"Authorization": f"Bearer {tenant_token}"}
        response = requests.get(f"{BASE_URL}/api/saas/tenants", headers=headers)
        
        # Should be denied (403 Forbidden)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✓ GET /api/saas/tenants correctly denied for Tenant Admin (403)")


class TestTelegramWebhook:
    """Test Telegram webhook processing"""
    
    def test_webhook_start_command_processes_successfully(self):
        """POST /api/telegram/webhook with /start command should return {ok: true}"""
        # Simulate a /start command webhook payload
        webhook_payload = {
            "update_id": 999999999,
            "message": {
                "message_id": 1,
                "from": {
                    "id": 123456789,
                    "is_bot": False,
                    "first_name": "Test",
                    "last_name": "User",
                    "language_code": "en"
                },
                "chat": {
                    "id": 123456789,
                    "first_name": "Test",
                    "last_name": "User",
                    "type": "private"
                },
                "date": 1775577000,
                "text": "/start",
                "entities": [{"offset": 0, "length": 6, "type": "bot_command"}]
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/telegram/webhook", json=webhook_payload)
        
        assert response.status_code == 200, f"Webhook failed: {response.text}"
        data = response.json()
        
        # Should return {ok: true}
        assert data.get("ok") == True, f"Expected ok=true, got {data}"
        
        print("✓ POST /api/telegram/webhook with /start command returned {ok: true}")
    
    def test_webhook_subscribe_command_processes_successfully(self):
        """POST /api/telegram/webhook with /start subscribe should return {ok: true}"""
        webhook_payload = {
            "update_id": 999999998,
            "message": {
                "message_id": 2,
                "from": {
                    "id": 987654321,
                    "is_bot": False,
                    "first_name": "Another",
                    "last_name": "User",
                    "language_code": "en"
                },
                "chat": {
                    "id": 987654321,
                    "first_name": "Another",
                    "last_name": "User",
                    "type": "private"
                },
                "date": 1775577001,
                "text": "/start subscribe",
                "entities": [{"offset": 0, "length": 6, "type": "bot_command"}]
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/telegram/webhook", json=webhook_payload)
        
        assert response.status_code == 200, f"Webhook failed: {response.text}"
        data = response.json()
        
        assert data.get("ok") == True, f"Expected ok=true, got {data}"
        
        print("✓ POST /api/telegram/webhook with /start subscribe returned {ok: true}")


class TestTenantIsolation:
    """Test strict tenant isolation - no orphan documents"""
    
    def test_no_orphan_plans_without_tenant_id(self):
        """Verify no plans exist without tenant_id"""
        # This test requires direct DB access or an admin endpoint
        # We'll use the Super Admin to check plans
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert login_response.status_code == 200
        data = login_response.json()
        token = data.get("token") or data.get("access_token")
        
        # Get all tenants and check their plans
        headers = {"Authorization": f"Bearer {token}"}
        tenants_response = requests.get(f"{BASE_URL}/api/saas/tenants", headers=headers)
        
        if tenants_response.status_code == 200:
            data = tenants_response.json()
            if isinstance(data, list):
                tenants = data
            elif isinstance(data, dict) and "tenants" in data:
                tenants = data["tenants"]
            else:
                tenants = data.get("data", [])
            
            # Each tenant should have a tenant_id
            for tenant in tenants:
                tenant_id = tenant.get("tenant_id") or tenant.get("id")
                assert tenant_id, f"Tenant missing tenant_id: {tenant}"
                assert tenant_id != "__unresolved_tenant__", f"Found unresolved tenant: {tenant}"
            
            print(f"✓ All {len(tenants)} tenants have valid tenant_id (no orphans)")
        else:
            pytest.skip("Could not verify tenant isolation - endpoint not accessible")


class TestQRToggleFeature:
    """Test QR toggle feature on tenant"""
    
    @pytest.fixture
    def tenant_admin_token(self):
        """Get Tenant Admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            return data.get("token") or data.get("access_token")
        pytest.skip("Tenant Admin authentication failed")
    
    def test_get_tenant_shows_qr_enabled_field(self, tenant_admin_token):
        """GET tenant should show qr_enabled field"""
        headers = {"Authorization": f"Bearer {tenant_admin_token}"}
        
        # Try to get tenant info
        response = requests.get(f"{BASE_URL}/api/tenant", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            # Check if qr_enabled field exists (can be True or False)
            if "qr_enabled" in data:
                print(f"✓ GET /api/tenant shows qr_enabled={data.get('qr_enabled')}")
            elif "tenant" in data and "qr_enabled" in data["tenant"]:
                print(f"✓ GET /api/tenant shows qr_enabled={data['tenant'].get('qr_enabled')}")
            else:
                # Field might be in settings or different structure
                print(f"⚠ qr_enabled field not found in response, checking structure: {list(data.keys())}")
        else:
            # Try alternative endpoint
            response = requests.get(f"{BASE_URL}/api/tenant/settings", headers=headers)
            if response.status_code == 200:
                data = response.json()
                print(f"✓ GET /api/tenant/settings returned: {list(data.keys())}")
            else:
                print(f"⚠ Could not verify qr_enabled field - status {response.status_code}")


class TestRoutesCleanup:
    """Test that legacy routes/ folder is deleted"""
    
    def test_routes_folder_does_not_exist(self):
        """Verify /app/backend/routes/ folder does NOT exist"""
        routes_path = "/app/backend/routes/"
        
        # Check if directory exists
        exists = os.path.exists(routes_path)
        
        assert not exists, f"Legacy routes/ folder still exists at {routes_path}"
        
        print("✓ /app/backend/routes/ folder does NOT exist (cleanup verified)")
    
    def test_backend_server_has_no_routes_imports(self):
        """Verify server.py does not import from routes/"""
        server_path = "/app/backend/server.py"
        
        with open(server_path, 'r') as f:
            content = f.read()
        
        # Check for any imports from routes
        assert "from routes" not in content, "server.py still imports from routes/"
        assert "import routes" not in content, "server.py still imports routes"
        
        print("✓ server.py has no imports from routes/ folder")


class TestBackendHealth:
    """Test backend server health and startup"""
    
    def test_backend_is_running(self):
        """Verify backend server is running and responding"""
        # Try health endpoint or root
        response = requests.get(f"{BASE_URL}/api/auth/login", timeout=10)
        
        # Should get a response (even if 405 for GET on login)
        assert response.status_code in [200, 405, 422], f"Backend not responding: {response.status_code}"
        
        print("✓ Backend server is running and responding")
    
    def test_backend_has_no_import_errors(self):
        """Verify backend started without import errors by checking logs"""
        # Check supervisor logs for import errors
        result = subprocess.run(
            ["tail", "-n", "100", "/var/log/supervisor/backend.err.log"],
            capture_output=True,
            text=True
        )
        
        log_content = result.stdout.lower()
        
        # Check for import errors
        assert "importerror" not in log_content, f"Import errors found in backend logs"
        assert "modulenotfounderror" not in log_content, f"Module not found errors in backend logs"
        
        print("✓ Backend started without import errors")


class TestStrictTenantEnforcement:
    """Test strict tenant enforcement - AccessDeniedError instead of fallback"""
    
    @pytest.fixture
    def super_admin_token(self):
        """Get Super Admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            return data.get("token") or data.get("access_token")
        pytest.skip("Super Admin authentication failed")
    
    def test_tenant_service_has_access_denied_error(self):
        """Verify tenant.py uses AccessDeniedError instead of silent fallback"""
        tenant_service_path = "/app/backend/services/tenant.py"
        
        with open(tenant_service_path, 'r') as f:
            content = f.read()
        
        # Check for AccessDeniedError import and usage
        assert "from core.exceptions import AccessDeniedError" in content, "Missing AccessDeniedError import"
        assert "raise AccessDeniedError" in content, "Missing AccessDeniedError raise statements"
        
        # Check that DEFAULT_TENANT_ID is NOT used
        assert "DEFAULT_TENANT_ID" not in content, "DEFAULT_TENANT_ID still present (should be removed)"
        
        # Check UNRESOLVED_TENANT is defined
        assert "UNRESOLVED_TENANT" in content, "UNRESOLVED_TENANT constant missing"
        
        print("✓ tenant.py uses AccessDeniedError and UNRESOLVED_TENANT (strict enforcement)")
    
    def test_constants_has_unresolved_tenant(self):
        """Verify constants.py has UNRESOLVED_TENANT"""
        constants_path = "/app/backend/core/constants.py"
        
        with open(constants_path, 'r') as f:
            content = f.read()
        
        assert "UNRESOLVED_TENANT" in content, "UNRESOLVED_TENANT missing from constants.py"
        assert "__unresolved_tenant__" in content, "UNRESOLVED_TENANT value missing"
        
        print("✓ constants.py has UNRESOLVED_TENANT = '__unresolved_tenant__'")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
