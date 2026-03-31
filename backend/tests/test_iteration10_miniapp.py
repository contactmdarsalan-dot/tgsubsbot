"""
Iteration 10 - Mini App Tests
Testing: QR code generation, UPI details, inline payment section, scrollable bottom sheet
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://glassmorphism-web-1.preview.emergentagent.com')


class TestMiniAppUPIDetails:
    """Test UPI details endpoint for Mini App"""
    
    def test_upi_details_returns_correct_upi_id(self):
        """GET /api/miniapp/upi-details should return correct UPI ID"""
        response = requests.get(f"{BASE_URL}/api/miniapp/upi-details")
        assert response.status_code == 200
        
        data = response.json()
        assert "upi_id" in data
        assert data["upi_id"] == "miraclecouplee@oksbi"
        print(f"✅ UPI ID: {data['upi_id']}")
    
    def test_upi_details_returns_qr_code_url(self):
        """GET /api/miniapp/upi-details should return QR code URL"""
        response = requests.get(f"{BASE_URL}/api/miniapp/upi-details")
        assert response.status_code == 200
        
        data = response.json()
        assert "qr_code_url" in data
        assert data["qr_code_url"] is not None
        assert len(data["qr_code_url"]) > 0
        print(f"✅ QR Code URL: {data['qr_code_url']}")
    
    def test_qr_code_file_is_accessible(self):
        """QR code file should be accessible and return 200"""
        # First get the QR URL
        response = requests.get(f"{BASE_URL}/api/miniapp/upi-details")
        data = response.json()
        qr_url = data.get("qr_code_url", "")
        
        # Build full URL if relative
        if qr_url.startswith("/"):
            full_qr_url = f"{BASE_URL}{qr_url}"
        else:
            full_qr_url = qr_url
        
        # Check if QR file is accessible
        qr_response = requests.get(full_qr_url)
        assert qr_response.status_code == 200
        assert "image" in qr_response.headers.get("content-type", "")
        print(f"✅ QR code file accessible: {full_qr_url}")
    
    def test_qr_code_is_auto_generated_from_upi_id(self):
        """QR code should be auto-generated from UPI ID (filename contains UPI ID)"""
        response = requests.get(f"{BASE_URL}/api/miniapp/upi-details")
        data = response.json()
        
        qr_url = data.get("qr_code_url", "")
        upi_id = data.get("upi_id", "")
        
        # The auto-generated QR should have UPI ID in filename
        # e.g., qr_auto_miraclecouplee_oksbi.png
        upi_id_normalized = upi_id.replace("@", "_")
        assert upi_id_normalized in qr_url or "qr_auto" in qr_url
        print(f"✅ QR code is auto-generated: {qr_url}")


class TestMiniAppPlans:
    """Test plans endpoint for Mini App"""
    
    def test_get_plans_returns_list(self):
        """GET /api/miniapp/plans should return list of plans"""
        response = requests.get(f"{BASE_URL}/api/miniapp/plans")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        print(f"✅ Found {len(data)} plans")
    
    def test_plans_have_required_fields(self):
        """Each plan should have id, name, price, duration_days"""
        response = requests.get(f"{BASE_URL}/api/miniapp/plans")
        data = response.json()
        
        for plan in data:
            assert "id" in plan
            assert "name" in plan
            assert "price" in plan
            assert "duration_days" in plan
        print("✅ All plans have required fields")


class TestMiniAppPhoneLogin:
    """Test phone login for Mini App"""
    
    def test_phone_login_with_valid_phone(self):
        """POST /api/miniapp/phone-login should return success with 20% discount"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/phone-login",
            json={
                "phone": "9876543210",
                "telegram_user_id": "test_iter10_user",
                "telegram_username": "test_user"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert data.get("discount") == 20
        print(f"✅ Phone login successful, discount: {data.get('discount')}%")
    
    def test_phone_login_with_invalid_phone(self):
        """POST /api/miniapp/phone-login with short phone should fail"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/phone-login",
            json={
                "phone": "123",
                "telegram_user_id": "test_iter10_invalid",
                "telegram_username": ""
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == False
        print("✅ Invalid phone correctly rejected")


class TestMiniAppCoupon:
    """Test coupon validation for Mini App"""
    
    def test_apply_invalid_coupon(self):
        """POST /api/miniapp/apply-coupon with invalid code should fail"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/apply-coupon",
            json={
                "code": "INVALIDCODE123",
                "plan_id": "test_plan",
                "amount": 999
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("valid") == False
        print("✅ Invalid coupon correctly rejected")


class TestMiniAppNotifications:
    """Test notifications endpoint"""
    
    def test_get_notifications(self):
        """GET /api/miniapp/notifications/{user_id} should return list"""
        response = requests.get(f"{BASE_URL}/api/miniapp/notifications/test_user_123")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Notifications endpoint works, found {len(data)} notifications")


class TestMiniAppSupportChat:
    """Test AI support chat"""
    
    def test_support_chat_responds(self):
        """POST /api/miniapp/support/chat should return AI response"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/support/chat",
            json={
                "telegram_user_id": "test_iter10_chat",
                "message": "What plans do you have?",
                "session_id": "test_session_iter10"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "reply" in data
        assert len(data["reply"]) > 0
        print(f"✅ Support chat responded: {data['reply'][:50]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
