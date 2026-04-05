"""
Iteration 35: Enhanced Tenant Management Tests
Tests for:
- GET /api/saas/all-users-dropdown - returns list of all users for dropdown
- PUT /api/saas/tenants/{tenant_id}/change-owner - changes tenant owner
- DELETE /api/saas/tenants/{tenant_id}/permanent - permanently deletes tenant and all data
- PUT /api/saas/tenants/{tenant_id}/reactivate - reactivates inactive tenant
- GET /api/saas/tenant-isolation-report - generates data isolation report
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"
SUPER_ADMIN_PASSWORD = "Sumit@8958"
TENANT_ADMIN_EMAIL = "anamika@test.com"
TENANT_ADMIN_PASSWORD = "Admin123"


@pytest.fixture(scope="module")
def super_admin_token():
    """Get super admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Super admin login failed: {response.text}"
    return response.json()["token"]


@pytest.fixture(scope="module")
def tenant_admin_token():
    """Get tenant admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TENANT_ADMIN_EMAIL,
        "password": TENANT_ADMIN_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip("Tenant admin login failed - skipping tenant admin tests")
    return response.json()["token"]


@pytest.fixture
def auth_headers(super_admin_token):
    """Auth headers for super admin"""
    return {"Authorization": f"Bearer {super_admin_token}"}


@pytest.fixture
def tenant_auth_headers(tenant_admin_token):
    """Auth headers for tenant admin"""
    return {"Authorization": f"Bearer {tenant_admin_token}"}


class TestAllUsersDropdown:
    """Tests for GET /api/saas/all-users-dropdown"""

    def test_get_all_users_dropdown_success(self, auth_headers):
        """Super admin can get all users for dropdown"""
        response = requests.get(f"{BASE_URL}/api/saas/all-users-dropdown", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        users = response.json()
        assert isinstance(users, list), "Response should be a list"
        
        # Verify user structure
        if len(users) > 0:
            user = users[0]
            assert "id" in user or "email" in user, "User should have id or email"
            # Should NOT contain password fields
            assert "password" not in user, "Should not expose password"
            assert "password_hash" not in user, "Should not expose password_hash"

    def test_get_all_users_dropdown_requires_auth(self):
        """Endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/saas/all-users-dropdown")
        assert response.status_code in [401, 403], "Should require auth"

    def test_get_all_users_dropdown_requires_super_admin(self, tenant_auth_headers):
        """Endpoint requires super admin role"""
        response = requests.get(f"{BASE_URL}/api/saas/all-users-dropdown", headers=tenant_auth_headers)
        assert response.status_code in [401, 403], "Should require super admin"


class TestChangeOwner:
    """Tests for PUT /api/saas/tenants/{tenant_id}/change-owner"""

    def test_change_owner_requires_auth(self):
        """Endpoint requires authentication"""
        response = requests.put(f"{BASE_URL}/api/saas/tenants/test_tenant/change-owner", json={
            "email": "new@owner.com"
        })
        assert response.status_code in [401, 403], "Should require auth"

    def test_change_owner_requires_super_admin(self, tenant_auth_headers):
        """Endpoint requires super admin role"""
        response = requests.put(
            f"{BASE_URL}/api/saas/tenants/test_tenant/change-owner",
            headers=tenant_auth_headers,
            json={"email": "new@owner.com"}
        )
        assert response.status_code in [401, 403], "Should require super admin"

    def test_change_owner_requires_email(self, auth_headers):
        """Email is required for change owner"""
        # First get a valid tenant
        tenants_resp = requests.get(f"{BASE_URL}/api/saas/tenants", headers=auth_headers)
        if tenants_resp.status_code != 200 or len(tenants_resp.json()) == 0:
            pytest.skip("No tenants available for testing")
        
        tenant_id = tenants_resp.json()[0]["tenant_id"]
        
        response = requests.put(
            f"{BASE_URL}/api/saas/tenants/{tenant_id}/change-owner",
            headers=auth_headers,
            json={}
        )
        assert response.status_code == 400, f"Should require email: {response.text}"

    def test_change_owner_tenant_not_found(self, auth_headers):
        """Returns 404 for non-existent tenant"""
        response = requests.put(
            f"{BASE_URL}/api/saas/tenants/nonexistent_tenant_xyz/change-owner",
            headers=auth_headers,
            json={"email": "new@owner.com"}
        )
        assert response.status_code == 404, f"Should return 404: {response.text}"

    def test_change_owner_success(self, auth_headers):
        """Successfully change tenant owner"""
        # Get tenants
        tenants_resp = requests.get(f"{BASE_URL}/api/saas/tenants", headers=auth_headers)
        if tenants_resp.status_code != 200 or len(tenants_resp.json()) == 0:
            pytest.skip("No tenants available for testing")
        
        tenant = tenants_resp.json()[0]
        tenant_id = tenant["tenant_id"]
        original_email = tenant.get("email", "")
        
        # Change owner to a test email
        test_email = f"test_owner_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.put(
            f"{BASE_URL}/api/saas/tenants/{tenant_id}/change-owner",
            headers=auth_headers,
            json={
                "email": test_email,
                "name": "Test Owner",
                "owner_telegram_id": "123456789"
            }
        )
        assert response.status_code == 200, f"Change owner failed: {response.text}"
        
        updated = response.json()
        assert updated.get("email") == test_email, "Email should be updated"
        
        # Revert back to original
        if original_email:
            requests.put(
                f"{BASE_URL}/api/saas/tenants/{tenant_id}/change-owner",
                headers=auth_headers,
                json={"email": original_email}
            )


class TestReactivateTenant:
    """Tests for PUT /api/saas/tenants/{tenant_id}/reactivate"""

    def test_reactivate_requires_auth(self):
        """Endpoint requires authentication"""
        response = requests.put(f"{BASE_URL}/api/saas/tenants/test_tenant/reactivate")
        assert response.status_code in [401, 403], "Should require auth"

    def test_reactivate_requires_super_admin(self, tenant_auth_headers):
        """Endpoint requires super admin role"""
        response = requests.put(
            f"{BASE_URL}/api/saas/tenants/test_tenant/reactivate",
            headers=tenant_auth_headers
        )
        assert response.status_code in [401, 403], "Should require super admin"

    def test_reactivate_tenant_not_found(self, auth_headers):
        """Returns 404 for non-existent tenant"""
        response = requests.put(
            f"{BASE_URL}/api/saas/tenants/nonexistent_tenant_xyz/reactivate",
            headers=auth_headers
        )
        assert response.status_code == 404, f"Should return 404: {response.text}"

    def test_reactivate_tenant_success(self, auth_headers):
        """Successfully reactivate a tenant"""
        # Get tenants
        tenants_resp = requests.get(f"{BASE_URL}/api/saas/tenants", headers=auth_headers)
        if tenants_resp.status_code != 200 or len(tenants_resp.json()) == 0:
            pytest.skip("No tenants available for testing")
        
        # Find an inactive tenant or use first one
        tenants = tenants_resp.json()
        inactive_tenant = next((t for t in tenants if t.get("status") == "inactive"), None)
        
        if inactive_tenant:
            tenant_id = inactive_tenant["tenant_id"]
            response = requests.put(
                f"{BASE_URL}/api/saas/tenants/{tenant_id}/reactivate",
                headers=auth_headers
            )
            assert response.status_code == 200, f"Reactivate failed: {response.text}"
            data = response.json()
            assert data.get("success") == True, "Should return success"
        else:
            # Test with active tenant - should still work (idempotent)
            tenant_id = tenants[0]["tenant_id"]
            response = requests.put(
                f"{BASE_URL}/api/saas/tenants/{tenant_id}/reactivate",
                headers=auth_headers
            )
            assert response.status_code == 200, f"Reactivate failed: {response.text}"


class TestPermanentDelete:
    """Tests for DELETE /api/saas/tenants/{tenant_id}/permanent"""

    def test_permanent_delete_requires_auth(self):
        """Endpoint requires authentication"""
        response = requests.delete(f"{BASE_URL}/api/saas/tenants/test_tenant/permanent")
        assert response.status_code in [401, 403], "Should require auth"

    def test_permanent_delete_requires_super_admin(self, tenant_auth_headers):
        """Endpoint requires super admin role"""
        response = requests.delete(
            f"{BASE_URL}/api/saas/tenants/test_tenant/permanent",
            headers=tenant_auth_headers
        )
        assert response.status_code in [401, 403], "Should require super admin"

    def test_permanent_delete_tenant_not_found(self, auth_headers):
        """Returns 404 for non-existent tenant"""
        response = requests.delete(
            f"{BASE_URL}/api/saas/tenants/nonexistent_tenant_xyz/permanent",
            headers=auth_headers
        )
        assert response.status_code == 404, f"Should return 404: {response.text}"

    def test_permanent_delete_creates_and_deletes_test_tenant(self, auth_headers):
        """Create a test tenant and permanently delete it"""
        # Create a test tenant
        test_tenant_name = f"TEST_DELETE_{uuid.uuid4().hex[:8]}"
        create_resp = requests.post(
            f"{BASE_URL}/api/saas/tenants",
            headers=auth_headers,
            json={
                "name": test_tenant_name,
                "email": f"test_delete_{uuid.uuid4().hex[:8]}@test.com"
            }
        )
        
        if create_resp.status_code != 200:
            pytest.skip(f"Could not create test tenant: {create_resp.text}")
        
        tenant_id = create_resp.json().get("tenant_id")
        assert tenant_id, "Should return tenant_id"
        
        # Now permanently delete it
        delete_resp = requests.delete(
            f"{BASE_URL}/api/saas/tenants/{tenant_id}/permanent",
            headers=auth_headers
        )
        assert delete_resp.status_code == 200, f"Delete failed: {delete_resp.text}"
        
        data = delete_resp.json()
        assert data.get("success") == True, "Should return success"
        assert "deleted_data" in data, "Should return deleted_data counts"
        
        # Verify tenant is gone
        verify_resp = requests.get(f"{BASE_URL}/api/saas/tenants", headers=auth_headers)
        tenants = verify_resp.json()
        tenant_ids = [t.get("tenant_id") for t in tenants]
        assert tenant_id not in tenant_ids, "Tenant should be deleted"


class TestTenantIsolationReport:
    """Tests for GET /api/saas/tenant-isolation-report"""

    def test_isolation_report_requires_auth(self):
        """Endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/saas/tenant-isolation-report")
        assert response.status_code in [401, 403], "Should require auth"

    def test_isolation_report_requires_super_admin(self, tenant_auth_headers):
        """Endpoint requires super admin role"""
        response = requests.get(
            f"{BASE_URL}/api/saas/tenant-isolation-report",
            headers=tenant_auth_headers
        )
        assert response.status_code in [401, 403], "Should require super admin"

    def test_isolation_report_success(self, auth_headers):
        """Successfully get isolation report"""
        response = requests.get(
            f"{BASE_URL}/api/saas/tenant-isolation-report",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        report = response.json()
        
        # Verify report structure
        assert "generated_at" in report, "Should have generated_at"
        assert "total_tenants" in report, "Should have total_tenants"
        assert "tenants" in report, "Should have tenants list"
        assert "orphaned_data" in report, "Should have orphaned_data"
        assert "cross_tenant_issues" in report, "Should have cross_tenant_issues"
        assert "summary" in report, "Should have summary"
        
        # Verify summary structure
        summary = report["summary"]
        assert "total_orphaned_records" in summary, "Summary should have total_orphaned_records"
        assert "total_cross_tenant_issues" in summary, "Summary should have total_cross_tenant_issues"
        assert "isolation_status" in summary, "Summary should have isolation_status"
        assert summary["isolation_status"] in ["CLEAN", "ISSUES_FOUND"], "Invalid isolation_status"

    def test_isolation_report_tenant_data_counts(self, auth_headers):
        """Verify tenant data counts in report"""
        response = requests.get(
            f"{BASE_URL}/api/saas/tenant-isolation-report",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        report = response.json()
        tenants = report.get("tenants", [])
        
        if len(tenants) > 0:
            tenant = tenants[0]
            assert "tenant_id" in tenant, "Tenant should have tenant_id"
            assert "name" in tenant, "Tenant should have name"
            assert "status" in tenant, "Tenant should have status"
            assert "data_counts" in tenant, "Tenant should have data_counts"
            
            data_counts = tenant["data_counts"]
            # Verify expected collections are counted
            expected_collections = ["bot_users", "subscribers", "payments", "plans"]
            for coll in expected_collections:
                assert coll in data_counts, f"data_counts should have {coll}"


class TestExistingTenantEndpoints:
    """Tests for existing tenant CRUD endpoints to ensure they still work"""

    def test_get_all_tenants(self, auth_headers):
        """GET /api/saas/tenants returns list of tenants"""
        response = requests.get(f"{BASE_URL}/api/saas/tenants", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        tenants = response.json()
        assert isinstance(tenants, list), "Should return list"
        
        if len(tenants) > 0:
            tenant = tenants[0]
            assert "tenant_id" in tenant, "Tenant should have tenant_id"
            assert "name" in tenant or "email" in tenant, "Tenant should have name or email"

    def test_deactivate_and_reactivate_flow(self, auth_headers):
        """Test deactivate then reactivate flow"""
        # Get tenants
        tenants_resp = requests.get(f"{BASE_URL}/api/saas/tenants", headers=auth_headers)
        if tenants_resp.status_code != 200 or len(tenants_resp.json()) == 0:
            pytest.skip("No tenants available for testing")
        
        # Find an active tenant that's not the main one
        tenants = tenants_resp.json()
        test_tenant = next((t for t in tenants if t.get("status") == "active" and t.get("name", "").startswith("TEST")), None)
        
        if not test_tenant:
            # Create a test tenant for this flow
            create_resp = requests.post(
                f"{BASE_URL}/api/saas/tenants",
                headers=auth_headers,
                json={
                    "name": f"TEST_FLOW_{uuid.uuid4().hex[:8]}",
                    "email": f"test_flow_{uuid.uuid4().hex[:8]}@test.com"
                }
            )
            if create_resp.status_code != 200:
                pytest.skip("Could not create test tenant")
            test_tenant = create_resp.json()
        
        tenant_id = test_tenant["tenant_id"]
        
        # Deactivate
        deactivate_resp = requests.delete(
            f"{BASE_URL}/api/saas/tenants/{tenant_id}",
            headers=auth_headers
        )
        assert deactivate_resp.status_code == 200, f"Deactivate failed: {deactivate_resp.text}"
        
        # Verify deactivated
        tenants_resp = requests.get(f"{BASE_URL}/api/saas/tenants", headers=auth_headers)
        tenant = next((t for t in tenants_resp.json() if t["tenant_id"] == tenant_id), None)
        assert tenant and tenant.get("status") == "inactive", "Tenant should be inactive"
        
        # Reactivate
        reactivate_resp = requests.put(
            f"{BASE_URL}/api/saas/tenants/{tenant_id}/reactivate",
            headers=auth_headers
        )
        assert reactivate_resp.status_code == 200, f"Reactivate failed: {reactivate_resp.text}"
        
        # Verify reactivated
        tenants_resp = requests.get(f"{BASE_URL}/api/saas/tenants", headers=auth_headers)
        tenant = next((t for t in tenants_resp.json() if t["tenant_id"] == tenant_id), None)
        assert tenant and tenant.get("status") == "active", "Tenant should be active"
        
        # Cleanup - permanently delete test tenant
        requests.delete(f"{BASE_URL}/api/saas/tenants/{tenant_id}/permanent", headers=auth_headers)


class TestIntegration:
    """Integration tests for the complete tenant management flow"""

    def test_full_tenant_lifecycle(self, auth_headers):
        """Test complete tenant lifecycle: create -> update -> change owner -> deactivate -> reactivate -> delete"""
        # 1. Create tenant
        tenant_name = f"TEST_LIFECYCLE_{uuid.uuid4().hex[:8]}"
        create_resp = requests.post(
            f"{BASE_URL}/api/saas/tenants",
            headers=auth_headers,
            json={
                "name": tenant_name,
                "email": f"lifecycle_{uuid.uuid4().hex[:8]}@test.com"
            }
        )
        assert create_resp.status_code == 200, f"Create failed: {create_resp.text}"
        tenant_id = create_resp.json()["tenant_id"]
        
        # 2. Update tenant
        update_resp = requests.put(
            f"{BASE_URL}/api/saas/tenants/{tenant_id}",
            headers=auth_headers,
            json={"name": f"{tenant_name}_UPDATED"}
        )
        assert update_resp.status_code == 200, f"Update failed: {update_resp.text}"
        
        # 3. Change owner
        new_email = f"new_owner_{uuid.uuid4().hex[:8]}@test.com"
        change_resp = requests.put(
            f"{BASE_URL}/api/saas/tenants/{tenant_id}/change-owner",
            headers=auth_headers,
            json={"email": new_email, "name": "New Owner"}
        )
        assert change_resp.status_code == 200, f"Change owner failed: {change_resp.text}"
        
        # 4. Deactivate
        deactivate_resp = requests.delete(
            f"{BASE_URL}/api/saas/tenants/{tenant_id}",
            headers=auth_headers
        )
        assert deactivate_resp.status_code == 200, f"Deactivate failed: {deactivate_resp.text}"
        
        # 5. Reactivate
        reactivate_resp = requests.put(
            f"{BASE_URL}/api/saas/tenants/{tenant_id}/reactivate",
            headers=auth_headers
        )
        assert reactivate_resp.status_code == 200, f"Reactivate failed: {reactivate_resp.text}"
        
        # 6. Permanent delete
        delete_resp = requests.delete(
            f"{BASE_URL}/api/saas/tenants/{tenant_id}/permanent",
            headers=auth_headers
        )
        assert delete_resp.status_code == 200, f"Delete failed: {delete_resp.text}"
        
        # Verify deleted
        tenants_resp = requests.get(f"{BASE_URL}/api/saas/tenants", headers=auth_headers)
        tenant_ids = [t["tenant_id"] for t in tenants_resp.json()]
        assert tenant_id not in tenant_ids, "Tenant should be permanently deleted"
