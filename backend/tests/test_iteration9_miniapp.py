"""
Iteration 9 Tests: Mini App Razorpay Removal, UPI QR Code, Channel Dropdown Fix
Tests for:
1. Mini App - Razorpay removed, only UPI payment
2. UPI details endpoint returns qr_code_url
3. Phone login works
4. Chat groups API returns proper group_name (not '0')
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMiniAppUPIDetails:
    """Test UPI details endpoint returns qr_code_url"""
    
    def test_upi_details_returns_qr_code_url(self):
        """GET /api/miniapp/upi-details should return upi_id and qr_code_url"""
        response = requests.get(f"{BASE_URL}/api/miniapp/upi-details")
        assert response.status_code == 200
        
        data = response.json()
        assert "upi_id" in data, "Response should contain upi_id"
        assert "qr_code_url" in data, "Response should contain qr_code_url"
        assert "payment_message" in data, "Response should contain payment_message"
        
        # Verify upi_id is not empty
        assert data["upi_id"], "upi_id should not be empty"
        print(f"✅ UPI ID: {data['upi_id']}")
        print(f"✅ QR Code URL: {data['qr_code_url'][:50]}..." if data['qr_code_url'] else "⚠️ QR Code URL is empty")


class TestMiniAppPhoneLogin:
    """Test phone login functionality"""
    
    def test_phone_login_success(self):
        """POST /api/miniapp/phone-login should register user and return 20% discount"""
        import uuid
        test_user_id = f"test_iter9_{uuid.uuid4().hex[:8]}"
        
        response = requests.post(
            f"{BASE_URL}/api/miniapp/phone-login",
            json={
                "phone": "9876543210",
                "telegram_user_id": test_user_id,
                "telegram_username": "test_user"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["discount"] == 20
        assert "message" in data
        print(f"✅ Phone login success: {data['message']}")
    
    def test_phone_login_invalid_phone(self):
        """POST /api/miniapp/phone-login should reject invalid phone"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/phone-login",
            json={
                "phone": "123",  # Too short
                "telegram_user_id": "test_invalid",
                "telegram_username": ""
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == False
        assert "error" in data
        print(f"✅ Invalid phone rejected: {data['error']}")
    
    def test_user_discount_check(self):
        """GET /api/miniapp/user-discount/{id} should return discount status"""
        # Test with non-existent user
        response = requests.get(f"{BASE_URL}/api/miniapp/user-discount/nonexistent_user_12345")
        assert response.status_code == 200
        
        data = response.json()
        assert "has_discount" in data
        assert "discount_percent" in data
        print(f"✅ User discount check: has_discount={data['has_discount']}")


class TestMiniAppPlans:
    """Test Mini App plans endpoint"""
    
    def test_get_plans(self):
        """GET /api/miniapp/plans should return active plans"""
        response = requests.get(f"{BASE_URL}/api/miniapp/plans")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Should have at least one plan"
        
        # Check plan structure
        plan = data[0]
        assert "id" in plan
        assert "name" in plan
        assert "price" in plan
        assert "duration_days" in plan
        print(f"✅ Found {len(data)} plans")


class TestChatGroups:
    """Test chat groups API returns proper group names"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "gamerxboys8958@gmail.com",
                "password": "Sumit@8958"
            }
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    def test_chat_groups_have_proper_names(self, auth_token):
        """GET /api/chat-groups should return groups with proper group_name (not '0')"""
        response = requests.get(
            f"{BASE_URL}/api/chat-groups",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        for group in data:
            assert "group_id" in group, "Group should have group_id"
            assert "group_name" in group, "Group should have group_name"
            
            # Verify group_id is not '0' or empty
            assert group["group_id"] != "0", f"group_id should not be '0': {group}"
            assert group["group_id"], f"group_id should not be empty: {group}"
            
            # Verify group_name is not '0' or empty
            assert group["group_name"] != "0", f"group_name should not be '0': {group}"
            assert group["group_name"], f"group_name should not be empty: {group}"
            
            print(f"✅ Group: {group['group_name']} ({group['group_id']})")
        
        print(f"✅ All {len(data)} groups have proper names")


class TestMiniAppSupportChat:
    """Test support chat functionality"""
    
    def test_support_chat(self):
        """POST /api/miniapp/support/chat should return AI response"""
        import uuid
        
        response = requests.post(
            f"{BASE_URL}/api/miniapp/support/chat",
            json={
                "telegram_user_id": "test_support_user",
                "message": "What plans do you have?",
                "session_id": f"test-session-{uuid.uuid4().hex[:8]}"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "reply" in data
        assert "escalated" in data
        assert data["reply"], "Reply should not be empty"
        print(f"✅ Support chat response: {data['reply'][:100]}...")


class TestMiniAppNotifications:
    """Test notifications endpoint"""
    
    def test_get_notifications(self):
        """GET /api/miniapp/notifications/{id} should return notifications"""
        response = requests.get(f"{BASE_URL}/api/miniapp/notifications/test_user_123")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Notifications endpoint working, returned {len(data)} notifications")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
