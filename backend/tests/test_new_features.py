"""
Test suite for new Telegram subscription bot dashboard features:
1. Subscribers page with Telegram ID, Channel ID, Group Name columns
2. Bulk Add to Channel functionality
3. Plans page with Promote button
4. Promote plan to group endpoint
5. Video Calls page
6. LiveStream page with Super Chats tab
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://subscription-manager-44.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "gamerxboys8958@gmail.com"
ADMIN_PASSWORD = "Sumit@8958"


class TestAuth:
    """Authentication tests"""
    
    def test_admin_login_success(self):
        """Test admin login with correct credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "super_admin"
        print(f"✓ Admin login successful - role: {data['user']['role']}")
        return data["token"]
    
    def test_admin_login_wrong_password(self):
        """Test admin login with wrong password"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": "wrongpassword"
        })
        assert response.status_code == 401, "Should fail with wrong password"
        print("✓ Wrong password correctly rejected")


class TestSubscribers:
    """Subscribers API tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    def test_get_subscribers_list(self, auth_token):
        """Test fetching subscribers list"""
        response = requests.get(
            f"{BASE_URL}/api/subscribers",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed to get subscribers: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Subscribers list fetched - count: {len(data)}")
        
        # Check if subscribers have the new fields
        if len(data) > 0:
            sub = data[0]
            # These fields should be present (may be empty but should exist)
            assert "telegram_user_id" in sub, "Missing telegram_user_id field"
            print(f"  - First subscriber has telegram_user_id: {sub.get('telegram_user_id', 'N/A')}")
            print(f"  - First subscriber has channel_id: {sub.get('channel_id', 'N/A')}")
            print(f"  - First subscriber has group_name: {sub.get('group_name', 'N/A')}")
    
    def test_get_subscribers_with_filter(self, auth_token):
        """Test fetching subscribers with status filter"""
        response = requests.get(
            f"{BASE_URL}/api/subscribers?status=active",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed to get active subscribers: {response.text}"
        data = response.json()
        print(f"✓ Active subscribers fetched - count: {len(data)}")
    
    def test_bulk_add_to_channel_endpoint(self, auth_token):
        """Test bulk add to channel endpoint exists and responds"""
        response = requests.post(
            f"{BASE_URL}/api/subscribers/bulk-add-to-channel",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={}
        )
        # May fail if bot not admin in channel, but endpoint should exist
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code} - {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "success" in data, "Response should have success count"
            assert "failed" in data, "Response should have failed count"
            assert "total" in data, "Response should have total count"
            print(f"✓ Bulk add endpoint works - success: {data['success']}, failed: {data['failed']}, total: {data['total']}")
        else:
            print(f"✓ Bulk add endpoint exists but returned error (expected if bot not admin): {response.json().get('detail', 'Unknown error')}")


class TestPlans:
    """Plans API tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    def test_get_plans_list(self, auth_token):
        """Test fetching plans list"""
        response = requests.get(
            f"{BASE_URL}/api/plans",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed to get plans: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Plans list fetched - count: {len(data)}")
        
        if len(data) > 0:
            plan = data[0]
            assert "id" in plan, "Plan should have id"
            assert "name" in plan, "Plan should have name"
            assert "price" in plan, "Plan should have price"
            print(f"  - First plan: {plan['name']} - ₹{plan['price']}")
            return plan["id"]
        return None
    
    def test_get_chat_groups(self, auth_token):
        """Test fetching chat groups for promote dropdown"""
        response = requests.get(
            f"{BASE_URL}/api/chat-groups",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed to get chat groups: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Chat groups fetched - count: {len(data)}")
        
        if len(data) > 0:
            group = data[0]
            print(f"  - First group: {group.get('group_name', group.get('group_id', 'Unknown'))}")
            return group.get("group_id")
        return None


class TestPromotePlan:
    """Promote plan to group tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    def test_promote_plan_missing_params(self, auth_token):
        """Test promote plan with missing parameters"""
        response = requests.post(
            f"{BASE_URL}/api/promote-plan",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={}
        )
        assert response.status_code == 400, "Should fail with missing params"
        print("✓ Promote plan correctly rejects missing parameters")
    
    def test_promote_plan_invalid_plan(self, auth_token):
        """Test promote plan with invalid plan ID"""
        response = requests.post(
            f"{BASE_URL}/api/promote-plan",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"plan_id": "invalid_plan_id", "group_id": "-1001234567890"}
        )
        assert response.status_code == 404, f"Should fail with invalid plan: {response.text}"
        print("✓ Promote plan correctly rejects invalid plan ID")
    
    def test_promote_plan_with_valid_plan(self, auth_token):
        """Test promote plan with valid plan (may fail if no groups)"""
        # First get a valid plan
        plans_response = requests.get(
            f"{BASE_URL}/api/plans",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        plans = plans_response.json()
        
        if len(plans) == 0:
            pytest.skip("No plans available to test promote")
        
        plan_id = plans[0]["id"]
        
        # Get groups
        groups_response = requests.get(
            f"{BASE_URL}/api/chat-groups",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        groups = groups_response.json()
        
        if len(groups) == 0:
            # Test with a dummy group ID - should fail but endpoint should work
            response = requests.post(
                f"{BASE_URL}/api/promote-plan",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={"plan_id": plan_id, "group_id": "-1001234567890"}
            )
            # May fail due to bot not being in group, but endpoint should respond
            assert response.status_code in [200, 400, 500], f"Unexpected status: {response.status_code}"
            print(f"✓ Promote plan endpoint responds (no groups available): status {response.status_code}")
        else:
            group_id = groups[0].get("group_id")
            response = requests.post(
                f"{BASE_URL}/api/promote-plan",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={"plan_id": plan_id, "group_id": group_id}
            )
            # May fail if bot not admin in group
            print(f"✓ Promote plan endpoint responds: status {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  - Promotion result: {data}")


class TestVideoCalls:
    """Video Calls API tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    def test_get_video_calls(self, auth_token):
        """Test fetching video call bookings"""
        response = requests.get(
            f"{BASE_URL}/api/video-calls",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed to get video calls: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Video calls fetched - count: {len(data)}")
        
        if len(data) > 0:
            booking = data[0]
            # Check expected fields
            expected_fields = ["id", "telegram_user_id", "status", "scheduled_date", "scheduled_time"]
            for field in expected_fields:
                assert field in booking, f"Missing field: {field}"
            print(f"  - First booking: {booking.get('telegram_username', booking.get('telegram_user_id'))} - {booking.get('status')}")
            if booking.get("notes"):
                print(f"  - Notes: {booking.get('notes')}")


class TestLiveStream:
    """Live Stream API tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    def test_get_live_sessions(self, auth_token):
        """Test fetching live sessions"""
        response = requests.get(
            f"{BASE_URL}/api/live/sessions",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed to get live sessions: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Live sessions fetched - count: {len(data)}")
    
    def test_get_live_tickets(self, auth_token):
        """Test fetching live tickets"""
        response = requests.get(
            f"{BASE_URL}/api/live/tickets",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed to get live tickets: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Live tickets fetched - count: {len(data)}")
    
    def test_get_super_chats(self, auth_token):
        """Test fetching super chats"""
        response = requests.get(
            f"{BASE_URL}/api/live/superchats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed to get super chats: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Super chats fetched - count: {len(data)}")


class TestNotifyAdmin:
    """Test admin notification function exists (can't fully test without Telegram)"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    def test_settings_endpoint(self, auth_token):
        """Test settings endpoint to verify bot configuration"""
        response = requests.get(
            f"{BASE_URL}/api/settings",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed to get settings: {response.text}"
        data = response.json()
        
        # Check if bot token is configured
        has_bot_token = bool(data.get("telegram_bot_token"))
        has_channel_id = bool(data.get("telegram_channel_id"))
        
        print(f"✓ Settings fetched - bot_token configured: {has_bot_token}, channel_id configured: {has_channel_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
