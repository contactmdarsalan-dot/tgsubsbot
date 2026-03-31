"""
Mini App Backend API Tests
Tests for: Plans, Status, Coupon, Support Chat, Referral, Payments, Notifications
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMiniAppPlans:
    """Test GET /api/miniapp/plans - Public endpoint"""
    
    def test_get_plans_returns_list(self):
        """Plans endpoint should return a list of active plans"""
        response = requests.get(f"{BASE_URL}/api/miniapp/plans")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✅ GET /api/miniapp/plans - Found {len(data)} plans")
        
        # Verify plan structure if plans exist
        if len(data) > 0:
            plan = data[0]
            assert "id" in plan, "Plan should have 'id'"
            assert "name" in plan, "Plan should have 'name'"
            assert "price" in plan, "Plan should have 'price'"
            assert "duration_days" in plan, "Plan should have 'duration_days'"
            print(f"✅ Plan structure verified: {plan.get('name')} - ₹{plan.get('price')}")


class TestMiniAppStatus:
    """Test GET /api/miniapp/status/{telegram_user_id}"""
    
    def test_get_status_no_subscription(self):
        """Status for non-existent user should return is_active: false"""
        fake_user_id = f"test_{uuid.uuid4().hex[:8]}"
        response = requests.get(f"{BASE_URL}/api/miniapp/status/{fake_user_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "is_active" in data, "Response should have 'is_active'"
        assert data["is_active"] == False, "Non-existent user should have is_active=False"
        print(f"✅ GET /api/miniapp/status/{fake_user_id} - No active subscription")
    
    def test_get_status_valid_format(self):
        """Status endpoint should return proper structure"""
        response = requests.get(f"{BASE_URL}/api/miniapp/status/123456789")
        assert response.status_code == 200
        
        data = response.json()
        assert "is_active" in data
        print(f"✅ Status response structure valid: is_active={data.get('is_active')}")


class TestMiniAppCoupon:
    """Test POST /api/miniapp/apply-coupon"""
    
    def test_apply_coupon_empty_code(self):
        """Empty coupon code should return error"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/apply-coupon",
            json={"code": "", "plan_id": "test", "amount": 100}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("valid") == False, "Empty code should be invalid"
        assert "error" in data, "Should have error message"
        print(f"✅ Empty coupon rejected: {data.get('error')}")
    
    def test_apply_coupon_invalid_code(self):
        """Invalid coupon code should return error"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/apply-coupon",
            json={"code": "INVALIDCODE123", "plan_id": "test", "amount": 100}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("valid") == False, "Invalid code should be invalid"
        print(f"✅ Invalid coupon rejected: {data.get('error')}")
    
    def test_apply_coupon_structure(self):
        """Coupon response should have proper structure"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/apply-coupon",
            json={"code": "TEST", "plan_id": "test", "amount": 100}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "valid" in data, "Response should have 'valid' field"
        print(f"✅ Coupon response structure valid")


class TestMiniAppSupportChat:
    """Test POST /api/miniapp/support/chat - AI Support"""
    
    def test_support_chat_empty_message(self):
        """Empty message should return default response"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/support/chat",
            json={"telegram_user_id": "test123", "message": ""}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "reply" in data, "Response should have 'reply'"
        assert "escalated" in data, "Response should have 'escalated'"
        print(f"✅ Empty message handled: {data.get('reply')[:50]}...")
    
    def test_support_chat_valid_message(self):
        """Valid message should get AI response"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/support/chat",
            json={
                "telegram_user_id": "test_user_123",
                "message": "What plans do you have?",
                "session_id": f"test-session-{uuid.uuid4().hex[:8]}"
            },
            timeout=30  # AI response may take time
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "reply" in data, "Response should have 'reply'"
        assert isinstance(data["reply"], str), "Reply should be a string"
        assert len(data["reply"]) > 0, "Reply should not be empty"
        assert "escalated" in data, "Response should have 'escalated'"
        print(f"✅ AI Support Chat response: {data.get('reply')[:80]}...")
    
    def test_support_chat_history(self):
        """Support chat history endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/miniapp/support/history/test_user_123")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "History should be a list"
        print(f"✅ Support chat history: {len(data)} messages")


class TestMiniAppReferral:
    """Test Referral endpoints"""
    
    def test_get_referral_code(self):
        """Get or create referral code for user"""
        test_user_id = f"test_ref_{uuid.uuid4().hex[:8]}"
        response = requests.get(f"{BASE_URL}/api/miniapp/referral/{test_user_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "referral_code" in data, "Response should have 'referral_code'"
        assert "referred_count" in data, "Response should have 'referred_count'"
        assert "referrer_reward" in data, "Response should have 'referrer_reward'"
        assert "referee_reward" in data, "Response should have 'referee_reward'"
        print(f"✅ Referral code generated: {data.get('referral_code')}")
    
    def test_apply_referral_missing_data(self):
        """Apply referral with missing data should fail"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/referral/apply",
            json={"code": "", "telegram_user_id": ""}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("valid") == False, "Missing data should be invalid"
        print(f"✅ Missing referral data rejected: {data.get('error')}")
    
    def test_apply_referral_invalid_code(self):
        """Apply invalid referral code should fail"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/referral/apply",
            json={"code": "INVALIDREF123", "telegram_user_id": "test_user"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("valid") == False, "Invalid code should be invalid"
        print(f"✅ Invalid referral code rejected: {data.get('error')}")
    
    def test_apply_own_referral_code(self):
        """User cannot use their own referral code"""
        # First get user's referral code
        test_user_id = f"test_own_{uuid.uuid4().hex[:8]}"
        get_response = requests.get(f"{BASE_URL}/api/miniapp/referral/{test_user_id}")
        assert get_response.status_code == 200
        
        ref_code = get_response.json().get("referral_code")
        
        # Try to apply own code
        apply_response = requests.post(
            f"{BASE_URL}/api/miniapp/referral/apply",
            json={"code": ref_code, "telegram_user_id": test_user_id}
        )
        assert apply_response.status_code == 200
        
        data = apply_response.json()
        assert data.get("valid") == False, "Own code should be invalid"
        print(f"✅ Own referral code rejected: {data.get('error')}")


class TestMiniAppPayments:
    """Test Payment History endpoint"""
    
    def test_get_payment_history_empty(self):
        """Payment history for new user should be empty"""
        fake_user_id = f"test_pay_{uuid.uuid4().hex[:8]}"
        response = requests.get(f"{BASE_URL}/api/miniapp/payments/{fake_user_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✅ Payment history for new user: {len(data)} payments")
    
    def test_get_payment_history_structure(self):
        """Payment history endpoint should return proper structure"""
        response = requests.get(f"{BASE_URL}/api/miniapp/payments/123456789")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✅ Payment history structure valid")


class TestMiniAppNotifications:
    """Test Notifications endpoint"""
    
    def test_get_notifications(self):
        """Get notifications for user"""
        response = requests.get(f"{BASE_URL}/api/miniapp/notifications/test_user_123")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✅ Notifications: {len(data)} items")
        
        # Verify notification structure if any exist
        if len(data) > 0:
            notif = data[0]
            assert "id" in notif, "Notification should have 'id'"
            assert "type" in notif, "Notification should have 'type'"
            assert "title" in notif, "Notification should have 'title'"
            assert "message" in notif, "Notification should have 'message'"
            print(f"✅ Notification structure valid: {notif.get('title')}")


class TestMiniAppRazorpayOrder:
    """Test Razorpay order creation (will fail without valid Razorpay account)"""
    
    def test_create_order_missing_plan(self):
        """Create order with non-existent plan should fail"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/create-order",
            json={
                "plan_id": "non_existent_plan_123",
                "telegram_user_id": "test_user",
                "amount": 100
            }
        )
        # Should return 404 for non-existent plan
        assert response.status_code in [404, 400, 500], f"Expected error status, got {response.status_code}"
        print(f"✅ Non-existent plan rejected: {response.status_code}")


class TestMiniAppMenuButton:
    """Test Menu Button endpoints"""
    
    def test_get_menu_button_status(self):
        """Get menu button status"""
        response = requests.get(f"{BASE_URL}/api/miniapp/menu-button-status")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data, "Response should have 'status'"
        print(f"✅ Menu button status: {data.get('status')}")
    
    def test_set_menu_button_missing_url(self):
        """Set menu button without URL should fail"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/set-menu-button",
            json={"text": "Menu"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"✅ Missing URL rejected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
