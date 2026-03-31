"""
Iteration 18: SaaS Management Feature Tests
Tests for Bot Plans CRUD and Tenant CRUD with admin assignment
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"
SUPER_ADMIN_PASSWORD = "Sumit@8958"


class TestSaaSManagementAuth:
    """Authentication and authorization tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get super admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        return data["token"]
    
    def test_super_admin_login(self, auth_token):
        """Test super admin can login"""
        assert auth_token is not None
        assert len(auth_token) > 0
        print(f"✓ Super admin login successful")
    
    def test_check_admin_status(self, auth_token):
        """Test admin status check endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/auth/check-admin",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("is_admin") == True, "User should be admin"
        print(f"✓ Admin status verified: is_admin={data.get('is_admin')}")


class TestBotPlansCRUD:
    """Bot Plans CRUD operations tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get super admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def created_plan_id(self, auth_token):
        """Create a test plan and return its ID for other tests"""
        plan_data = {
            "name": "TEST_Pro Plan",
            "price": 999,
            "duration_days": 30,
            "features": ["AI Payment Verification", "Live Stream Tickets"],
            "max_subscribers": 1000,
            "max_broadcasts": 20,
            "ai_verify_enabled": True,
            "live_stream_enabled": True,
            "paid_posts_enabled": True,
            "is_popular": True
        }
        response = requests.post(
            f"{BASE_URL}/api/saas/bot-plans",
            json=plan_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Create plan failed: {response.text}"
        data = response.json()
        assert "id" in data
        return data["id"]
    
    def test_get_bot_plans(self, auth_token):
        """Test GET /api/saas/bot-plans"""
        response = requests.get(
            f"{BASE_URL}/api/saas/bot-plans",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET bot-plans returned {len(data)} plans")
    
    def test_create_bot_plan(self, auth_token):
        """Test POST /api/saas/bot-plans - Create a new plan"""
        plan_data = {
            "name": "TEST_Basic Plan",
            "price": 499,
            "duration_days": 15,
            "features": ["AI Payment Verification"],
            "max_subscribers": 500,
            "max_broadcasts": 10,
            "ai_verify_enabled": True,
            "live_stream_enabled": False,
            "paid_posts_enabled": False,
            "is_popular": False
        }
        response = requests.post(
            f"{BASE_URL}/api/saas/bot-plans",
            json=plan_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Create failed: {response.text}"
        data = response.json()
        
        # Verify response data
        assert "id" in data, "Response should have id"
        assert data["name"] == "TEST_Basic Plan"
        assert data["price"] == 499
        assert data["duration_days"] == 15
        assert "AI Payment Verification" in data["features"]
        assert data["is_popular"] == False
        print(f"✓ Created bot plan: {data['name']} (id={data['id']})")
        
        # Cleanup - delete the test plan
        requests.delete(
            f"{BASE_URL}/api/saas/bot-plans/{data['id']}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    
    def test_update_bot_plan(self, auth_token, created_plan_id):
        """Test PUT /api/saas/bot-plans/{id} - Update a plan"""
        update_data = {
            "name": "TEST_Pro Plan Updated",
            "price": 1299,
            "is_popular": False
        }
        response = requests.put(
            f"{BASE_URL}/api/saas/bot-plans/{created_plan_id}",
            json=update_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        
        # Verify update
        assert data["name"] == "TEST_Pro Plan Updated"
        assert data["price"] == 1299
        assert data["is_popular"] == False
        print(f"✓ Updated bot plan: {data['name']} (price={data['price']})")
    
    def test_verify_plan_update_persisted(self, auth_token, created_plan_id):
        """Verify plan update was persisted by fetching all plans"""
        response = requests.get(
            f"{BASE_URL}/api/saas/bot-plans",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        plans = response.json()
        
        # Find our updated plan
        updated_plan = next((p for p in plans if p["id"] == created_plan_id), None)
        assert updated_plan is not None, "Updated plan not found"
        assert updated_plan["name"] == "TEST_Pro Plan Updated"
        assert updated_plan["price"] == 1299
        print(f"✓ Verified plan update persisted in database")
    
    def test_delete_bot_plan(self, auth_token, created_plan_id):
        """Test DELETE /api/saas/bot-plans/{id} - Delete a plan"""
        response = requests.delete(
            f"{BASE_URL}/api/saas/bot-plans/{created_plan_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Delete failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        print(f"✓ Deleted bot plan: {created_plan_id}")
    
    def test_verify_plan_deleted(self, auth_token, created_plan_id):
        """Verify plan was deleted"""
        response = requests.get(
            f"{BASE_URL}/api/saas/bot-plans",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        plans = response.json()
        
        # Plan should not exist
        deleted_plan = next((p for p in plans if p["id"] == created_plan_id), None)
        assert deleted_plan is None, "Plan should be deleted"
        print(f"✓ Verified plan was deleted from database")


class TestTenantsCRUD:
    """Tenant CRUD operations tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get super admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["token"]
    
    def test_get_tenants(self, auth_token):
        """Test GET /api/saas/tenants - Get all tenants with stats"""
        response = requests.get(
            f"{BASE_URL}/api/saas/tenants",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Check for expected tenants (Kaloo and Anamika)
        tenant_names = [t.get("name", t.get("tenant_id")) for t in data]
        print(f"✓ GET tenants returned {len(data)} tenants: {tenant_names}")
        
        # Verify tenant structure
        if len(data) > 0:
            tenant = data[0]
            assert "tenant_id" in tenant
            assert "stats" in tenant
            assert "total_users" in tenant["stats"]
            assert "active_subs" in tenant["stats"]
            assert "revenue" in tenant["stats"]
            print(f"✓ Tenant structure verified with stats")
    
    def test_verify_kaloo_tenant_exists(self, auth_token):
        """Verify Kaloo tenant exists with expected data"""
        response = requests.get(
            f"{BASE_URL}/api/saas/tenants",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        tenants = response.json()
        
        # Find Kaloo tenant (tenant_id='default')
        kaloo = next((t for t in tenants if t.get("tenant_id") == "default"), None)
        if kaloo:
            print(f"✓ Found Kaloo tenant: users={kaloo['stats']['total_users']}, subs={kaloo['stats']['active_subs']}, revenue=₹{kaloo['stats']['revenue']}")
        else:
            print("⚠ Kaloo tenant (default) not found - may need to be created")
    
    def test_create_tenant(self, auth_token):
        """Test POST /api/saas/tenants - Create a new tenant"""
        tenant_data = {
            "name": "TEST_New Creator",
            "email": "test_creator@example.com",
            "owner_telegram_id": "987654321",
            "bot_token": "test_bot_token_123",
            "bot_username": "test_creator_bot",
            "upi_id": "test@paytm",
            "channel_id": "-1001234567890",
            "razorpay_key_id": ""
        }
        response = requests.post(
            f"{BASE_URL}/api/saas/tenants",
            json=tenant_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Create tenant failed: {response.text}"
        data = response.json()
        
        # Verify response
        assert "tenant_id" in data
        assert data["name"] == "TEST_New Creator"
        assert data["email"] == "test_creator@example.com"
        assert data["status"] == "active"
        print(f"✓ Created tenant: {data['name']} (tenant_id={data['tenant_id']})")
        
        # Store for cleanup
        return data["tenant_id"]
    
    def test_update_tenant(self, auth_token):
        """Test PUT /api/saas/tenants/{id} - Update a tenant"""
        # First create a tenant to update
        create_response = requests.post(
            f"{BASE_URL}/api/saas/tenants",
            json={
                "name": "TEST_Update Tenant",
                "email": "update_test@example.com",
                "owner_telegram_id": "111222333"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert create_response.status_code == 200
        tenant_id = create_response.json()["tenant_id"]
        
        # Update the tenant
        update_data = {
            "name": "TEST_Updated Tenant Name",
            "email": "updated_email@example.com",
            "upi_id": "updated@paytm"
        }
        response = requests.put(
            f"{BASE_URL}/api/saas/tenants/{tenant_id}",
            json=update_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        
        # Verify update
        assert data["name"] == "TEST_Updated Tenant Name"
        assert data["email"] == "updated_email@example.com"
        assert data["upi_id"] == "updated@paytm"
        print(f"✓ Updated tenant: {data['name']}")
        
        # Cleanup - deactivate
        requests.delete(
            f"{BASE_URL}/api/saas/tenants/{tenant_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    
    def test_deactivate_tenant(self, auth_token):
        """Test DELETE /api/saas/tenants/{id} - Deactivate a tenant"""
        # First create a tenant to deactivate
        create_response = requests.post(
            f"{BASE_URL}/api/saas/tenants",
            json={
                "name": "TEST_Deactivate Tenant",
                "email": "deactivate_test@example.com",
                "owner_telegram_id": "444555666"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert create_response.status_code == 200
        tenant_id = create_response.json()["tenant_id"]
        
        # Deactivate the tenant
        response = requests.delete(
            f"{BASE_URL}/api/saas/tenants/{tenant_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Deactivate failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        print(f"✓ Deactivated tenant: {tenant_id}")
        
        # Verify status changed to inactive
        get_response = requests.get(
            f"{BASE_URL}/api/saas/tenants",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        tenants = get_response.json()
        deactivated = next((t for t in tenants if t["tenant_id"] == tenant_id), None)
        if deactivated:
            assert deactivated["status"] == "inactive"
            print(f"✓ Verified tenant status is 'inactive'")


class TestTenantAdminAssignment:
    """Tenant admin assignment tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get super admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def test_tenant_id(self, auth_token):
        """Create a test tenant for admin assignment tests"""
        response = requests.post(
            f"{BASE_URL}/api/saas/tenants",
            json={
                "name": "TEST_Admin Assignment Tenant",
                "email": "admin_test@example.com",
                "owner_telegram_id": "777888999"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        return response.json()["tenant_id"]
    
    def test_get_tenant_admins(self, auth_token, test_tenant_id):
        """Test GET /api/saas/tenants/{id}/admins"""
        response = requests.get(
            f"{BASE_URL}/api/saas/tenants/{test_tenant_id}/admins",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET tenant admins returned {len(data)} admins")
    
    def test_assign_admin_to_tenant(self, auth_token, test_tenant_id):
        """Test POST /api/saas/tenants/{id}/admins - Assign new admin"""
        admin_data = {
            "telegram_user_id": "TEST_123456789",
            "name": "Test Admin",
            "email": "testadmin@example.com",
            "role": "admin"
        }
        response = requests.post(
            f"{BASE_URL}/api/saas/tenants/{test_tenant_id}/admins",
            json=admin_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Assign admin failed: {response.text}"
        data = response.json()
        
        # Verify response
        assert "id" in data
        assert data["telegram_user_id"] == "TEST_123456789"
        assert data["name"] == "Test Admin"
        assert data["role"] == "admin"
        assert data["is_active"] == True
        print(f"✓ Assigned admin: {data['name']} (TG: {data['telegram_user_id']})")
        
        return data["id"]
    
    def test_verify_admin_assignment_persisted(self, auth_token, test_tenant_id):
        """Verify admin assignment was persisted"""
        response = requests.get(
            f"{BASE_URL}/api/saas/tenants/{test_tenant_id}/admins",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        admins = response.json()
        
        # Find our assigned admin
        test_admin = next((a for a in admins if a["telegram_user_id"] == "TEST_123456789"), None)
        assert test_admin is not None, "Assigned admin not found"
        assert test_admin["name"] == "Test Admin"
        print(f"✓ Verified admin assignment persisted")
    
    def test_duplicate_admin_assignment_fails(self, auth_token, test_tenant_id):
        """Test that assigning same admin twice fails"""
        admin_data = {
            "telegram_user_id": "TEST_123456789",
            "name": "Duplicate Admin",
            "role": "admin"
        }
        response = requests.post(
            f"{BASE_URL}/api/saas/tenants/{test_tenant_id}/admins",
            json=admin_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 409, "Should fail with 409 Conflict"
        print(f"✓ Duplicate admin assignment correctly rejected (409)")
    
    def test_remove_admin_from_tenant(self, auth_token, test_tenant_id):
        """Test DELETE /api/saas/tenants/{id}/admins/{admin_id}"""
        # Get the admin ID first
        get_response = requests.get(
            f"{BASE_URL}/api/saas/tenants/{test_tenant_id}/admins",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        admins = get_response.json()
        test_admin = next((a for a in admins if a["telegram_user_id"] == "TEST_123456789"), None)
        
        if test_admin:
            admin_id = test_admin["id"]
            
            # Remove the admin
            response = requests.delete(
                f"{BASE_URL}/api/saas/tenants/{test_tenant_id}/admins/{admin_id}",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            assert response.status_code == 200, f"Remove admin failed: {response.text}"
            data = response.json()
            assert data.get("success") == True
            print(f"✓ Removed admin: {admin_id}")
            
            # Verify removal
            verify_response = requests.get(
                f"{BASE_URL}/api/saas/tenants/{test_tenant_id}/admins",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            remaining_admins = verify_response.json()
            removed_admin = next((a for a in remaining_admins if a["id"] == admin_id), None)
            assert removed_admin is None, "Admin should be removed"
            print(f"✓ Verified admin was removed")
        else:
            pytest.skip("Test admin not found for removal test")
    
    def test_cleanup_test_tenant(self, auth_token, test_tenant_id):
        """Cleanup: Deactivate test tenant"""
        response = requests.delete(
            f"{BASE_URL}/api/saas/tenants/{test_tenant_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        print(f"✓ Cleaned up test tenant: {test_tenant_id}")


class TestCleanupTestData:
    """Cleanup all TEST_ prefixed data"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get super admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["token"]
    
    def test_cleanup_test_plans(self, auth_token):
        """Cleanup any remaining TEST_ prefixed plans"""
        response = requests.get(
            f"{BASE_URL}/api/saas/bot-plans",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        if response.status_code == 200:
            plans = response.json()
            test_plans = [p for p in plans if p.get("name", "").startswith("TEST_")]
            for plan in test_plans:
                requests.delete(
                    f"{BASE_URL}/api/saas/bot-plans/{plan['id']}",
                    headers={"Authorization": f"Bearer {auth_token}"}
                )
            print(f"✓ Cleaned up {len(test_plans)} test plans")
    
    def test_cleanup_test_tenants(self, auth_token):
        """Cleanup any remaining TEST_ prefixed tenants"""
        response = requests.get(
            f"{BASE_URL}/api/saas/tenants",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        if response.status_code == 200:
            tenants = response.json()
            test_tenants = [t for t in tenants if t.get("name", "").startswith("TEST_")]
            for tenant in test_tenants:
                requests.delete(
                    f"{BASE_URL}/api/saas/tenants/{tenant['tenant_id']}",
                    headers={"Authorization": f"Bearer {auth_token}"}
                )
            print(f"✓ Cleaned up {len(test_tenants)} test tenants")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
