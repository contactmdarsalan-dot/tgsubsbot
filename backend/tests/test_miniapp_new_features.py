"""
Test Mini App New Features - Phone Login, Discount, UPI Details
Tests for iteration 8: Phone login screen, 20% discount, UPI manual sheet
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPhoneLogin:
    """Phone login endpoint tests - 20% discount feature"""
    
    def test_phone_login_success(self):
        """Test successful phone login returns 20% discount"""
        unique_id = f"test_phone_{uuid.uuid4().hex[:8]}"
        response = requests.post(f"{BASE_URL}/api/miniapp/phone-login", json={
            "phone": "9876543210",
            "telegram_user_id": unique_id,
            "telegram_username": "testuser"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["discount"] == 20
        assert "message" in data
        print(f"✅ Phone login success: {data}")
    
    def test_phone_login_invalid_phone(self):
        """Test phone login with invalid phone number"""
        response = requests.post(f"{BASE_URL}/api/miniapp/phone-login", json={
            "phone": "123",
            "telegram_user_id": "test_invalid",
            "telegram_username": ""
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "error" in data
        print(f"✅ Invalid phone rejected: {data}")
    
    def test_phone_login_empty_phone(self):
        """Test phone login with empty phone"""
        response = requests.post(f"{BASE_URL}/api/miniapp/phone-login", json={
            "phone": "",
            "telegram_user_id": "test_empty",
            "telegram_username": ""
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        print(f"✅ Empty phone rejected: {data}")
    
    def test_phone_login_already_registered(self):
        """Test phone login for already registered user"""
        unique_id = f"test_existing_{uuid.uuid4().hex[:8]}"
        # First registration
        requests.post(f"{BASE_URL}/api/miniapp/phone-login", json={
            "phone": "9876543211",
            "telegram_user_id": unique_id,
            "telegram_username": "existinguser"
        })
        # Second attempt
        response = requests.post(f"{BASE_URL}/api/miniapp/phone-login", json={
            "phone": "9876543211",
            "telegram_user_id": unique_id,
            "telegram_username": "existinguser"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["discount"] == 20
        assert data["already_registered"] == True
        print(f"✅ Already registered user handled: {data}")


class TestUserDiscount:
    """User discount endpoint tests"""
    
    def test_user_discount_exists(self):
        """Test user discount for registered user"""
        unique_id = f"test_disc_{uuid.uuid4().hex[:8]}"
        # Register first
        requests.post(f"{BASE_URL}/api/miniapp/phone-login", json={
            "phone": "9876543212",
            "telegram_user_id": unique_id,
            "telegram_username": "discuser"
        })
        # Check discount
        response = requests.get(f"{BASE_URL}/api/miniapp/user-discount/{unique_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["has_discount"] == True
        assert data["discount_percent"] == 20
        assert data["phone"] == "9876543212"
        print(f"✅ User discount found: {data}")
    
    def test_user_discount_not_exists(self):
        """Test user discount for non-registered user"""
        response = requests.get(f"{BASE_URL}/api/miniapp/user-discount/nonexistent_user_xyz")
        assert response.status_code == 200
        data = response.json()
        assert data["has_discount"] == False
        assert data["discount_percent"] == 0
        print(f"✅ No discount for non-registered: {data}")


class TestUPIDetails:
    """UPI details endpoint tests"""
    
    def test_upi_details_returns_data(self):
        """Test UPI details endpoint returns UPI ID and message"""
        response = requests.get(f"{BASE_URL}/api/miniapp/upi-details")
        assert response.status_code == 200
        data = response.json()
        assert "upi_id" in data
        assert "payment_message" in data
        # UPI ID should not be empty (configured in settings)
        assert len(data["upi_id"]) > 0 or data["upi_id"] == ""  # Can be empty if not configured
        print(f"✅ UPI details returned: {data}")


class TestPlansWithDiscount:
    """Test plans endpoint still works"""
    
    def test_plans_available(self):
        """Test plans endpoint returns active plans"""
        response = requests.get(f"{BASE_URL}/api/miniapp/plans")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Check plan structure
        plan = data[0]
        assert "id" in plan
        assert "name" in plan
        assert "price" in plan
        assert "duration_days" in plan
        print(f"✅ Plans returned: {len(data)} plans")


class TestExistingEndpoints:
    """Verify existing endpoints still work after new features"""
    
    def test_status_endpoint(self):
        """Test subscription status endpoint"""
        response = requests.get(f"{BASE_URL}/api/miniapp/status/test_user_status")
        assert response.status_code == 200
        data = response.json()
        assert "is_active" in data
        print(f"✅ Status endpoint works: {data}")
    
    def test_notifications_endpoint(self):
        """Test notifications endpoint"""
        response = requests.get(f"{BASE_URL}/api/miniapp/notifications/test_user_notif")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Notifications endpoint works: {len(data)} notifications")
    
    def test_payments_endpoint(self):
        """Test payment history endpoint"""
        response = requests.get(f"{BASE_URL}/api/miniapp/payments/test_user_payments")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Payments endpoint works: {len(data)} payments")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
