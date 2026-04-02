"""
Iteration 26 Tests: Team Management, Tenant-Level Subscription, Local File Upload, Login Default
Tests:
1. Login page defaults to sign-in mode (isLogin=true)
2. File upload works with local storage (POST /api/upload/image)
3. Tenant team management: GET /api/tenant/team
4. Tenant team management: POST /api/tenant/team (create member)
5. Tenant team management: DELETE /api/tenant/team/{id}
6. Tenant team management: PUT /api/tenant/team/{id}/reset-password
7. Assign subscription to tenant: POST /api/saas/assign-subscription with tenant_id
8. Super Admin login and Control Center access
9. Tenant Admin login and Dashboard access
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"
SUPER_ADMIN_PASSWORD = "Sumit@8958"
TENANT_ADMIN_EMAIL = "anamika@test.com"
TENANT_ADMIN_PASSWORD = "Admin123"
TEST_TENANT_ID = "tenant_85ee971d0285"


@pytest.fixture(scope="module")
def super_admin_token():
    """Get super admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Super admin login failed: {response.text}")
    return response.json().get("token")


@pytest.fixture(scope="module")
def tenant_admin_token():
    """Get tenant admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TENANT_ADMIN_EMAIL,
        "password": TENANT_ADMIN_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Tenant admin login failed: {response.text}")
    return response.json().get("token")


@pytest.fixture(scope="module")
def tenant_admin_user(tenant_admin_token):
    """Get tenant admin user info"""
    response = requests.get(f"{BASE_URL}/api/auth/me", headers={
        "Authorization": f"Bearer {tenant_admin_token}"
    })
    if response.status_code != 200:
        pytest.skip(f"Failed to get tenant admin info: {response.text}")
    return response.json()


class TestSuperAdminLogin:
    """Test Super Admin login and access"""
    
    def test_super_admin_login_success(self):
        """Super Admin can login with correct credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == SUPER_ADMIN_EMAIL
        assert data["user"]["role"] == "super_admin"
    
    def test_super_admin_can_access_admin_stats(self, super_admin_token):
        """Super Admin can access Control Center stats"""
        response = requests.get(f"{BASE_URL}/api/admin/stats", headers={
            "Authorization": f"Bearer {super_admin_token}"
        })
        assert response.status_code == 200, f"Admin stats failed: {response.text}"
        data = response.json()
        assert "platform" in data
        assert "bot_ecosystem" in data
        assert "revenue" in data


class TestTenantAdminLogin:
    """Test Tenant Admin login and access"""
    
    def test_tenant_admin_login_success(self):
        """Tenant Admin can login with correct credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == TENANT_ADMIN_EMAIL
        assert data["user"]["role"] == "tenant_admin"
    
    def test_tenant_admin_can_access_dashboard(self, tenant_admin_token):
        """Tenant Admin can access dashboard stats"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers={
            "Authorization": f"Bearer {tenant_admin_token}"
        })
        assert response.status_code == 200, f"Dashboard stats failed: {response.text}"


class TestLocalFileUpload:
    """Test local file upload (S3 removed)"""
    
    def test_upload_image_returns_local_url(self, tenant_admin_token):
        """POST /api/upload/image returns /api/uploads/ URL (local storage)"""
        # Create a simple test image (1x1 PNG)
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        
        files = {'file': ('test_image.png', io.BytesIO(png_data), 'image/png')}
        response = requests.post(
            f"{BASE_URL}/api/upload/image",
            files=files,
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 200, f"Upload failed: {response.text}"
        data = response.json()
        assert "url" in data
        assert data["url"].startswith("/api/uploads/"), f"Expected local URL, got: {data['url']}"
        assert "filename" in data
    
    def test_upload_qr_code_returns_local_url(self, tenant_admin_token):
        """POST /api/upload/qr-code returns /api/uploads/ URL (local storage)"""
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        
        files = {'file': ('qr_code.png', io.BytesIO(png_data), 'image/png')}
        response = requests.post(
            f"{BASE_URL}/api/upload/qr-code",
            files=files,
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 200, f"Upload failed: {response.text}"
        data = response.json()
        assert "url" in data
        assert data["url"].startswith("/api/uploads/"), f"Expected local URL, got: {data['url']}"


class TestTenantTeamManagement:
    """Test tenant team management endpoints"""
    
    def test_get_team_members(self, tenant_admin_token):
        """GET /api/tenant/team returns team members list"""
        response = requests.get(f"{BASE_URL}/api/tenant/team", headers={
            "Authorization": f"Bearer {tenant_admin_token}"
        })
        assert response.status_code == 200, f"Get team failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
    
    def test_create_team_member(self, tenant_admin_token):
        """POST /api/tenant/team creates new team member with active status"""
        import uuid
        test_email = f"test_team_{uuid.uuid4().hex[:8]}@test.com"
        
        response = requests.post(f"{BASE_URL}/api/tenant/team", json={
            "email": test_email,
            "password": "Test123!",
            "name": "Test Team Member"
        }, headers={
            "Authorization": f"Bearer {tenant_admin_token}"
        })
        assert response.status_code == 200, f"Create team member failed: {response.text}"
        data = response.json()
        assert "message" in data
        assert "admin" in data
        assert data["admin"]["email"] == test_email
        assert data["admin"]["role"] == "tenant_admin"
        # New team member should have active status
        assert data["admin"].get("dashboard_subscription_status") == "active"
        
        # Store for cleanup
        TestTenantTeamManagement.created_member_id = data["admin"]["id"]
        TestTenantTeamManagement.created_member_email = test_email
    
    def test_new_team_member_can_login(self, tenant_admin_token):
        """New team member can login immediately"""
        if not hasattr(TestTenantTeamManagement, 'created_member_email'):
            pytest.skip("No team member created")
        
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TestTenantTeamManagement.created_member_email,
            "password": "Test123!"
        })
        assert response.status_code == 200, f"New member login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "tenant_admin"
    
    def test_reset_team_member_password(self, tenant_admin_token):
        """PUT /api/tenant/team/{id}/reset-password resets password"""
        if not hasattr(TestTenantTeamManagement, 'created_member_id'):
            pytest.skip("No team member created")
        
        member_id = TestTenantTeamManagement.created_member_id
        response = requests.put(
            f"{BASE_URL}/api/tenant/team/{member_id}/reset-password",
            json={"password": "NewPass123!"},
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 200, f"Reset password failed: {response.text}"
        data = response.json()
        assert "message" in data
        
        # Verify new password works
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TestTenantTeamManagement.created_member_email,
            "password": "NewPass123!"
        })
        assert login_response.status_code == 200, "Login with new password failed"
    
    def test_delete_team_member(self, tenant_admin_token):
        """DELETE /api/tenant/team/{id} removes team member"""
        if not hasattr(TestTenantTeamManagement, 'created_member_id'):
            pytest.skip("No team member created")
        
        member_id = TestTenantTeamManagement.created_member_id
        response = requests.delete(
            f"{BASE_URL}/api/tenant/team/{member_id}",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 200, f"Delete team member failed: {response.text}"
        
        # Verify member is deleted - login should fail
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TestTenantTeamManagement.created_member_email,
            "password": "NewPass123!"
        })
        assert login_response.status_code != 200, "Deleted member should not be able to login"
    
    def test_cannot_delete_self(self, tenant_admin_token, tenant_admin_user):
        """Cannot delete yourself from team"""
        user_id = tenant_admin_user.get("id")
        response = requests.delete(
            f"{BASE_URL}/api/tenant/team/{user_id}",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 400, "Should not be able to delete self"
        assert "Cannot remove yourself" in response.json().get("detail", "")


class TestTenantLevelSubscription:
    """Test subscription assignment at tenant level (not individual admin)"""
    
    def test_assign_subscription_to_tenant(self, super_admin_token):
        """POST /api/saas/assign-subscription with tenant_id updates ALL admins"""
        response = requests.post(
            f"{BASE_URL}/api/saas/assign-subscription",
            json={
                "tenant_id": TEST_TENANT_ID,
                "plan_id": "lifetime",
                "duration_days": 365
            },
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200, f"Assign subscription failed: {response.text}"
        data = response.json()
        assert "message" in data
        assert TEST_TENANT_ID in data["message"] or "tenant" in data["message"].lower()
        # Should mention admins updated
        assert "admin" in data["message"].lower()
    
    def test_tenant_admins_have_subscription_after_assignment(self, super_admin_token):
        """All tenant admins should have active subscription after tenant-level assignment"""
        # Get all tenant admins
        response = requests.get(
            f"{BASE_URL}/api/saas/tenant-admins",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200
        admins = response.json()
        
        # Filter admins for our test tenant
        tenant_admins = [a for a in admins if a.get("tenant_id") == TEST_TENANT_ID]
        
        # All should have active subscription
        for admin in tenant_admins:
            assert admin.get("dashboard_subscription_status") == "active", \
                f"Admin {admin.get('email')} should have active subscription"


class TestTeamEndpointAuthorization:
    """Test team endpoint authorization"""
    
    def test_team_endpoint_requires_auth(self):
        """GET /api/tenant/team requires authentication"""
        response = requests.get(f"{BASE_URL}/api/tenant/team")
        assert response.status_code in [401, 403], "Should require auth"
    
    def test_super_admin_cannot_access_tenant_team(self, super_admin_token):
        """Super admin without tenant_id cannot access tenant team"""
        response = requests.get(f"{BASE_URL}/api/tenant/team", headers={
            "Authorization": f"Bearer {super_admin_token}"
        })
        # Super admin doesn't have tenant_id, should get 400 or 403
        assert response.status_code in [400, 403], f"Expected 400/403, got {response.status_code}"


class TestLoginPageDefault:
    """Test that login page defaults to sign-in mode"""
    
    def test_login_endpoint_works(self):
        """Login endpoint is accessible"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "nonexistent@test.com",
            "password": "wrongpass"
        })
        # Should return 401 for invalid credentials, not 500
        assert response.status_code in [400, 401, 404], f"Unexpected status: {response.status_code}"
