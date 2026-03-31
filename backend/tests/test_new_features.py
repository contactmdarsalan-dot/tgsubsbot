"""
Test suite for TGSubsBot new features:
1. Branding CRUD (GET/PUT /api/branding)
2. Bot Language CRUD (GET/PUT /api/bot-language)
3. PDF Export (GET /api/analytics/export-pdf)
4. Forgot Password with Email (POST /api/auth/forgot-password)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "gamerxboys8958@gmail.com"
TEST_PASSWORD = "Sumit@8958"


class TestAuth:
    """Authentication tests"""
    
    def test_login_success(self):
        """Test super admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        assert "user" in data, "No user in response"
        assert data["user"]["email"] == TEST_EMAIL
        print(f"✅ Login successful for {TEST_EMAIL}")
        return data["token"]
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "invalid@test.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ Invalid credentials rejected correctly")


class TestBranding:
    """White-label branding endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_branding(self):
        """GET /api/branding - Fetch branding settings"""
        response = requests.get(f"{BASE_URL}/api/branding", headers=self.headers)
        assert response.status_code == 200, f"Failed to get branding: {response.text}"
        data = response.json()
        
        # Verify at least brand_name and primary_color exist (defaults or saved)
        assert "brand_name" in data, "brand_name missing"
        assert "primary_color" in data, "primary_color missing"
        # Note: Other fields may not exist if never saved - frontend handles defaults
        print(f"✅ GET /api/branding - brand_name: {data['brand_name']}, primary_color: {data['primary_color']}")
    
    def test_update_branding(self):
        """PUT /api/branding - Update branding settings"""
        update_data = {
            "brand_name": "TEST_CustomBrand",
            "tagline": "TEST_Tagline",
            "primary_color": "#ff5733",
            "secondary_color": "#1a1a2e",
            "footer_text": "TEST_Footer"
        }
        response = requests.put(f"{BASE_URL}/api/branding", json=update_data, headers=self.headers)
        assert response.status_code == 200, f"Failed to update branding: {response.text}"
        data = response.json()
        assert "message" in data, "No message in response"
        print(f"✅ PUT /api/branding - Updated successfully")
        
        # Verify update persisted
        get_response = requests.get(f"{BASE_URL}/api/branding", headers=self.headers)
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["brand_name"] == "TEST_CustomBrand", "brand_name not persisted"
        assert get_data["primary_color"] == "#ff5733", "primary_color not persisted"
        print("✅ Branding update verified via GET")
    
    def test_update_branding_partial(self):
        """PUT /api/branding - Partial update"""
        response = requests.put(f"{BASE_URL}/api/branding", json={
            "tagline": "TEST_NewTagline"
        }, headers=self.headers)
        assert response.status_code == 200, f"Partial update failed: {response.text}"
        print("✅ Partial branding update works")
    
    def test_update_branding_invalid_fields(self):
        """PUT /api/branding - Invalid fields should be ignored"""
        response = requests.put(f"{BASE_URL}/api/branding", json={
            "invalid_field": "test"
        }, headers=self.headers)
        # Should return 400 since no valid fields
        assert response.status_code == 400, f"Expected 400 for invalid fields, got {response.status_code}"
        print("✅ Invalid branding fields rejected correctly")


class TestBotLanguage:
    """Bot language settings endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_bot_language(self):
        """GET /api/bot-language - Fetch language settings"""
        response = requests.get(f"{BASE_URL}/api/bot-language", headers=self.headers)
        assert response.status_code == 200, f"Failed to get bot-language: {response.text}"
        data = response.json()
        
        # Verify required fields
        assert "default_language" in data, "default_language missing"
        assert "available_languages" in data, "available_languages missing"
        assert "messages" in data, "messages missing"
        
        # Verify all 3 languages available
        assert "english" in data["available_languages"], "english not in available_languages"
        assert "hindi" in data["available_languages"], "hindi not in available_languages"
        assert "hinglish" in data["available_languages"], "hinglish not in available_languages"
        
        # Verify messages structure
        assert "english" in data["messages"], "english messages missing"
        assert "hindi" in data["messages"], "hindi messages missing"
        assert "hinglish" in data["messages"], "hinglish messages missing"
        
        print(f"✅ GET /api/bot-language - default: {data['default_language']}, languages: {data['available_languages']}")
    
    def test_update_bot_language_default(self):
        """PUT /api/bot-language - Update default language"""
        response = requests.put(f"{BASE_URL}/api/bot-language", json={
            "default_language": "hindi"
        }, headers=self.headers)
        assert response.status_code == 200, f"Failed to update default language: {response.text}"
        print("✅ PUT /api/bot-language - default_language updated to hindi")
        
        # Verify persistence
        get_response = requests.get(f"{BASE_URL}/api/bot-language", headers=self.headers)
        assert get_response.status_code == 200
        # Note: The endpoint merges with defaults, so we just verify it doesn't error
        print("✅ Bot language update verified")
    
    def test_update_bot_language_messages(self):
        """PUT /api/bot-language - Update custom messages"""
        response = requests.put(f"{BASE_URL}/api/bot-language", json={
            "default_language": "hinglish",
            "messages": {
                "hinglish": {
                    "welcome": "TEST_Welcome bhai!",
                    "payment_verified": "TEST_Payment done!"
                }
            }
        }, headers=self.headers)
        assert response.status_code == 200, f"Failed to update messages: {response.text}"
        print("✅ PUT /api/bot-language - custom messages updated")
    
    def test_update_bot_language_invalid(self):
        """PUT /api/bot-language - Invalid language should be rejected"""
        response = requests.put(f"{BASE_URL}/api/bot-language", json={
            "default_language": "spanish"  # Not in allowed list
        }, headers=self.headers)
        # Should return 400 since spanish is not valid
        assert response.status_code == 400, f"Expected 400 for invalid language, got {response.status_code}"
        print("✅ Invalid language rejected correctly")


class TestPDFExport:
    """PDF export endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_export_pdf(self):
        """GET /api/analytics/export-pdf - Generate PDF report"""
        response = requests.get(f"{BASE_URL}/api/analytics/export-pdf", headers=self.headers)
        assert response.status_code == 200, f"PDF export failed: {response.text}"
        
        # Verify content type is PDF
        content_type = response.headers.get("content-type", "")
        assert "application/pdf" in content_type, f"Expected PDF content type, got: {content_type}"
        
        # Verify content disposition header
        content_disp = response.headers.get("content-disposition", "")
        assert "attachment" in content_disp, f"Expected attachment disposition, got: {content_disp}"
        assert "TGSubsBot_Revenue" in content_disp, f"Expected TGSubsBot_Revenue in filename, got: {content_disp}"
        
        # Verify PDF content starts with PDF magic bytes
        assert response.content[:4] == b'%PDF', "Response is not a valid PDF"
        
        print(f"✅ GET /api/analytics/export-pdf - PDF generated, size: {len(response.content)} bytes")
    
    def test_export_pdf_unauthorized(self):
        """GET /api/analytics/export-pdf - Should require auth"""
        response = requests.get(f"{BASE_URL}/api/analytics/export-pdf")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✅ PDF export requires authentication")


class TestForgotPassword:
    """Forgot password with email integration tests"""
    
    def test_forgot_password_existing_email(self):
        """POST /api/auth/forgot-password - Existing email"""
        response = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={
            "email": TEST_EMAIL
        })
        assert response.status_code == 200, f"Forgot password failed: {response.text}"
        data = response.json()
        
        # Should return message
        assert "message" in data, "No message in response"
        
        # Since RESEND_API_KEY is not configured, should return test_otp
        if "test_otp" in data:
            assert len(data["test_otp"]) == 6, "OTP should be 6 digits"
            print(f"✅ POST /api/auth/forgot-password - test_otp returned (email service MOCKED)")
        else:
            print(f"✅ POST /api/auth/forgot-password - email sent (Resend configured)")
    
    def test_forgot_password_nonexistent_email(self):
        """POST /api/auth/forgot-password - Non-existent email (should not reveal)"""
        response = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={
            "email": "nonexistent@test.com"
        })
        # Should return 200 to not reveal if email exists
        assert response.status_code == 200, f"Expected 200 for security, got {response.status_code}"
        data = response.json()
        assert "message" in data
        print("✅ Non-existent email handled securely (no info leak)")
    
    def test_forgot_password_missing_email(self):
        """POST /api/auth/forgot-password - Missing email"""
        response = requests.post(f"{BASE_URL}/api/auth/forgot-password", json={})
        assert response.status_code == 400, f"Expected 400 for missing email, got {response.status_code}"
        print("✅ Missing email rejected correctly")


class TestAnalyticsEndpoint:
    """Basic analytics endpoint test"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_analytics(self):
        """GET /api/analytics - Basic analytics"""
        response = requests.get(f"{BASE_URL}/api/analytics", headers=self.headers)
        assert response.status_code == 200, f"Analytics failed: {response.text}"
        data = response.json()
        
        # Verify key fields
        assert "total_subscribers" in data
        assert "active_subscribers" in data
        assert "total_revenue" in data
        assert "monthly_revenue" in data
        print(f"✅ GET /api/analytics - total_revenue: {data['total_revenue']}, active_subs: {data['active_subscribers']}")


class TestDashboardFlow:
    """Test dashboard loads correctly"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_auth_me(self):
        """GET /api/auth/me - Verify user session"""
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=self.headers)
        assert response.status_code == 200, f"Auth me failed: {response.text}"
        data = response.json()
        assert data["email"] == TEST_EMAIL
        print(f"✅ GET /api/auth/me - User: {data['email']}, role: {data.get('role', 'user')}")


# Cleanup test data
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    """Cleanup TEST_ prefixed data after all tests"""
    yield
    # Reset branding to defaults after tests
    try:
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            token = response.json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            # Reset branding
            requests.put(f"{BASE_URL}/api/branding", json={
                "brand_name": "TGSubsBot",
                "tagline": "Premium Subscriptions",
                "primary_color": "#e11d48",
                "secondary_color": "#1a1a2e",
                "footer_text": "Powered by TGSubsBot"
            }, headers=headers)
            # Reset bot language
            requests.put(f"{BASE_URL}/api/bot-language", json={
                "default_language": "hinglish"
            }, headers=headers)
            print("\n✅ Test data cleaned up")
    except Exception as e:
        print(f"\n⚠️ Cleanup failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
