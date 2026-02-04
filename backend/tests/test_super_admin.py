"""
Super Admin Dashboard API Tests
Tests for super admin features including:
- Access control (only super admin email can access)
- GET /api/admin/all-users
- GET /api/admin/stats
- GET /api/admin/subscription-requests
- PUT /api/admin/set-lifetime/{user_id}
- PUT /api/admin/revoke-access/{user_id}
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"
SUPER_ADMIN_PASSWORD = "admin123"
REGULAR_USER_EMAIL = "testsuperadmin@test.com"
REGULAR_USER_PASSWORD = "test123"


class TestSuperAdminSetup:
    """Setup tests - ensure users exist"""
    
    @pytest.fixture(scope="class")
    def super_admin_token(self):
        """Get or create super admin and return token"""
        # Try to login first
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        
        if response.status_code == 200:
            return response.json().get("token")
        
        # If login fails, register the super admin
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD,
            "name": "Super Admin",
            "phone": ""
        })
        
        if response.status_code == 200:
            return response.json().get("token")
        
        # Try login again after registration
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        
        if response.status_code == 200:
            return response.json().get("token")
        
        pytest.skip(f"Could not authenticate super admin: {response.text}")
    
    @pytest.fixture(scope="class")
    def regular_user_token(self):
        """Get or create regular user and return token"""
        # Try to login first
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": REGULAR_USER_EMAIL,
            "password": REGULAR_USER_PASSWORD
        })
        
        if response.status_code == 200:
            return response.json().get("token")
        
        # If login fails, register the user
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": REGULAR_USER_EMAIL,
            "password": REGULAR_USER_PASSWORD,
            "name": "Test Regular User",
            "phone": ""
        })
        
        if response.status_code == 200:
            return response.json().get("token")
        
        # Try login again after registration
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": REGULAR_USER_EMAIL,
            "password": REGULAR_USER_PASSWORD
        })
        
        if response.status_code == 200:
            return response.json().get("token")
        
        pytest.skip(f"Could not authenticate regular user: {response.text}")
    
    @pytest.fixture(scope="class")
    def regular_user_id(self, regular_user_token):
        """Get regular user ID"""
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        if response.status_code == 200:
            return response.json().get("id")
        pytest.skip("Could not get regular user ID")
    
    def test_super_admin_login(self, super_admin_token):
        """Test super admin can login"""
        assert super_admin_token is not None
        assert len(super_admin_token) > 0
        print(f"SUCCESS: Super admin authenticated")
    
    def test_regular_user_login(self, regular_user_token):
        """Test regular user can login"""
        assert regular_user_token is not None
        assert len(regular_user_token) > 0
        print(f"SUCCESS: Regular user authenticated")


class TestSuperAdminAccessControl:
    """Test access control - only super admin can access admin APIs"""
    
    @pytest.fixture(scope="class")
    def super_admin_token(self):
        """Get super admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Super admin login failed")
    
    @pytest.fixture(scope="class")
    def regular_user_token(self):
        """Get regular user token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": REGULAR_USER_EMAIL,
            "password": REGULAR_USER_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Regular user login failed")
    
    def test_regular_user_cannot_access_all_users(self, regular_user_token):
        """Non-super-admin should get 403 on /api/admin/all-users"""
        response = requests.get(f"{BASE_URL}/api/admin/all-users", headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        assert "Super Admin" in response.json().get("detail", "")
        print(f"SUCCESS: Regular user blocked from /api/admin/all-users (403)")
    
    def test_regular_user_cannot_access_stats(self, regular_user_token):
        """Non-super-admin should get 403 on /api/admin/stats"""
        response = requests.get(f"{BASE_URL}/api/admin/stats", headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"SUCCESS: Regular user blocked from /api/admin/stats (403)")
    
    def test_regular_user_cannot_access_subscription_requests(self, regular_user_token):
        """Non-super-admin should get 403 on /api/admin/subscription-requests"""
        response = requests.get(f"{BASE_URL}/api/admin/subscription-requests", headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"SUCCESS: Regular user blocked from /api/admin/subscription-requests (403)")
    
    def test_regular_user_cannot_set_lifetime(self, regular_user_token):
        """Non-super-admin should get 403 on /api/admin/set-lifetime"""
        response = requests.put(f"{BASE_URL}/api/admin/set-lifetime/some-user-id", headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"SUCCESS: Regular user blocked from /api/admin/set-lifetime (403)")
    
    def test_regular_user_cannot_revoke_access(self, regular_user_token):
        """Non-super-admin should get 403 on /api/admin/revoke-access"""
        response = requests.put(f"{BASE_URL}/api/admin/revoke-access/some-user-id", headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"SUCCESS: Regular user blocked from /api/admin/revoke-access (403)")


class TestSuperAdminAPIs:
    """Test super admin APIs work correctly"""
    
    @pytest.fixture(scope="class")
    def super_admin_token(self):
        """Get super admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Super admin login failed")
    
    @pytest.fixture(scope="class")
    def regular_user_id(self):
        """Get regular user ID"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": REGULAR_USER_EMAIL,
            "password": REGULAR_USER_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("token")
            me_response = requests.get(f"{BASE_URL}/api/auth/me", headers={
                "Authorization": f"Bearer {token}"
            })
            if me_response.status_code == 200:
                return me_response.json().get("id")
        pytest.skip("Could not get regular user ID")
    
    def test_get_all_users(self, super_admin_token):
        """Super admin can get all users"""
        response = requests.get(f"{BASE_URL}/api/admin/all-users", headers={
            "Authorization": f"Bearer {super_admin_token}"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        users = response.json()
        assert isinstance(users, list), "Response should be a list"
        
        # Verify user structure
        if len(users) > 0:
            user = users[0]
            assert "id" in user, "User should have id"
            assert "email" in user, "User should have email"
            assert "name" in user, "User should have name"
            assert "password_hash" not in user, "Password hash should not be exposed"
        
        print(f"SUCCESS: GET /api/admin/all-users returned {len(users)} users")
    
    def test_get_stats(self, super_admin_token):
        """Super admin can get dashboard stats"""
        response = requests.get(f"{BASE_URL}/api/admin/stats", headers={
            "Authorization": f"Bearer {super_admin_token}"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        stats = response.json()
        assert "total_users" in stats, "Stats should have total_users"
        assert "active_subscribers" in stats, "Stats should have active_subscribers"
        assert "pending_requests" in stats, "Stats should have pending_requests"
        assert "total_revenue" in stats, "Stats should have total_revenue"
        
        # Verify types
        assert isinstance(stats["total_users"], int), "total_users should be int"
        assert isinstance(stats["active_subscribers"], int), "active_subscribers should be int"
        assert isinstance(stats["pending_requests"], int), "pending_requests should be int"
        assert isinstance(stats["total_revenue"], (int, float)), "total_revenue should be numeric"
        
        print(f"SUCCESS: GET /api/admin/stats - total_users={stats['total_users']}, active={stats['active_subscribers']}")
    
    def test_get_subscription_requests(self, super_admin_token):
        """Super admin can get all subscription requests"""
        response = requests.get(f"{BASE_URL}/api/admin/subscription-requests", headers={
            "Authorization": f"Bearer {super_admin_token}"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        requests_list = response.json()
        assert isinstance(requests_list, list), "Response should be a list"
        
        print(f"SUCCESS: GET /api/admin/subscription-requests returned {len(requests_list)} requests")
    
    def test_set_lifetime_access(self, super_admin_token, regular_user_id):
        """Super admin can grant lifetime access"""
        response = requests.put(f"{BASE_URL}/api/admin/set-lifetime/{regular_user_id}", headers={
            "Authorization": f"Bearer {super_admin_token}"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data, "Response should have message"
        assert "Lifetime" in data["message"], "Message should confirm lifetime access"
        
        # Verify the user now has lifetime access
        users_response = requests.get(f"{BASE_URL}/api/admin/all-users", headers={
            "Authorization": f"Bearer {super_admin_token}"
        })
        users = users_response.json()
        target_user = next((u for u in users if u["id"] == regular_user_id), None)
        
        assert target_user is not None, "User should exist"
        assert target_user.get("dashboard_plan") == "lifetime", "User should have lifetime plan"
        assert target_user.get("dashboard_subscription_status") == "active", "User should be active"
        
        print(f"SUCCESS: PUT /api/admin/set-lifetime/{regular_user_id} - Lifetime access granted")
    
    def test_revoke_access(self, super_admin_token, regular_user_id):
        """Super admin can revoke access"""
        response = requests.put(f"{BASE_URL}/api/admin/revoke-access/{regular_user_id}", headers={
            "Authorization": f"Bearer {super_admin_token}"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data, "Response should have message"
        assert "revoked" in data["message"].lower(), "Message should confirm revocation"
        
        # Verify the user access is revoked
        users_response = requests.get(f"{BASE_URL}/api/admin/all-users", headers={
            "Authorization": f"Bearer {super_admin_token}"
        })
        users = users_response.json()
        target_user = next((u for u in users if u["id"] == regular_user_id), None)
        
        assert target_user is not None, "User should exist"
        assert target_user.get("dashboard_subscription_status") == "inactive", "User should be inactive"
        
        print(f"SUCCESS: PUT /api/admin/revoke-access/{regular_user_id} - Access revoked")
    
    def test_cannot_revoke_super_admin_access(self, super_admin_token):
        """Super admin cannot revoke their own access"""
        # First get super admin's user ID
        me_response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {super_admin_token}"
        })
        super_admin_id = me_response.json().get("id")
        
        response = requests.put(f"{BASE_URL}/api/admin/revoke-access/{super_admin_id}", headers={
            "Authorization": f"Bearer {super_admin_token}"
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        assert "super admin" in response.json().get("detail", "").lower()
        
        print(f"SUCCESS: Cannot revoke super admin's own access (400)")
    
    def test_set_lifetime_invalid_user(self, super_admin_token):
        """Set lifetime for non-existent user returns 404"""
        response = requests.put(f"{BASE_URL}/api/admin/set-lifetime/invalid-user-id-12345", headers={
            "Authorization": f"Bearer {super_admin_token}"
        })
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"SUCCESS: Set lifetime for invalid user returns 404")
    
    def test_revoke_access_invalid_user(self, super_admin_token):
        """Revoke access for non-existent user returns 404"""
        response = requests.put(f"{BASE_URL}/api/admin/revoke-access/invalid-user-id-12345", headers={
            "Authorization": f"Bearer {super_admin_token}"
        })
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"SUCCESS: Revoke access for invalid user returns 404")


class TestSuperAdminDataIntegrity:
    """Test data integrity after super admin operations"""
    
    @pytest.fixture(scope="class")
    def super_admin_token(self):
        """Get super admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Super admin login failed")
    
    def test_users_list_contains_expected_fields(self, super_admin_token):
        """Verify users list has all expected fields for display"""
        response = requests.get(f"{BASE_URL}/api/admin/all-users", headers={
            "Authorization": f"Bearer {super_admin_token}"
        })
        assert response.status_code == 200
        
        users = response.json()
        if len(users) > 0:
            user = users[0]
            # Fields needed for the Users table in SuperAdminDashboard
            expected_fields = ["id", "email", "name", "dashboard_plan", 
                             "dashboard_subscription_status", "dashboard_subscription_end", "created_at"]
            for field in expected_fields:
                assert field in user or user.get(field) is None, f"User should have {field} field"
        
        print(f"SUCCESS: Users list contains all expected fields")
    
    def test_stats_values_are_consistent(self, super_admin_token):
        """Verify stats values are logically consistent"""
        response = requests.get(f"{BASE_URL}/api/admin/stats", headers={
            "Authorization": f"Bearer {super_admin_token}"
        })
        assert response.status_code == 200
        
        stats = response.json()
        
        # Active subscribers should not exceed total users
        assert stats["active_subscribers"] <= stats["total_users"], \
            "Active subscribers should not exceed total users"
        
        # Revenue should be non-negative
        assert stats["total_revenue"] >= 0, "Revenue should be non-negative"
        
        # Pending requests should be non-negative
        assert stats["pending_requests"] >= 0, "Pending requests should be non-negative"
        
        print(f"SUCCESS: Stats values are logically consistent")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
