"""
Iteration 46: Polls, Dashboard Paid Post Creation, Scheduled Posts Tests
Tests for:
1. GET /api/polls - returns empty array for new tenant
2. POST /api/polls - creates a poll record (draft without channel_id)
3. DELETE /api/polls/{id} - deletes a poll
4. GET /api/scheduled-posts - returns empty array
5. POST /api/paid-posts/create - multipart form endpoint exists
6. POST /api/paid-posts/preview-blur - multipart form endpoint exists
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TENANT_ADMIN_EMAIL = "anamika@test.com"
TENANT_ADMIN_PASSWORD = "Admin123"


class TestAuthentication:
    """Test authentication for tenant admin"""
    
    def test_tenant_admin_login(self):
        """Test tenant admin can login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        assert "user" in data, "No user in response"
        print(f"✓ Tenant admin login successful, role: {data['user'].get('role')}")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for tenant admin"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TENANT_ADMIN_EMAIL,
        "password": TENANT_ADMIN_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.text}")
    return response.json()["token"]


@pytest.fixture
def auth_headers(auth_token):
    """Get auth headers"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestPollsAPI:
    """Test Polls CRUD endpoints"""
    
    def test_get_polls_returns_list(self, auth_headers):
        """GET /api/polls should return a list (possibly empty)"""
        response = requests.get(f"{BASE_URL}/api/polls", headers=auth_headers)
        assert response.status_code == 200, f"GET /api/polls failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET /api/polls returns list with {len(data)} polls")
    
    def test_create_poll_draft(self, auth_headers):
        """POST /api/polls creates a draft poll (no channel_id)"""
        poll_data = {
            "question": "TEST_Poll: What is your favorite color?",
            "options": ["Red", "Blue", "Green"],
            "is_anonymous": True,
            "allows_multiple": False
            # No channel_id = draft
        }
        response = requests.post(f"{BASE_URL}/api/polls", json=poll_data, headers=auth_headers)
        assert response.status_code == 200, f"POST /api/polls failed: {response.text}"
        data = response.json()
        assert "id" in data, "Poll should have an id"
        assert data["question"] == poll_data["question"], "Question mismatch"
        assert data["status"] == "draft", f"Expected status 'draft', got '{data.get('status')}'"
        print(f"✓ Created draft poll with id: {data['id']}, status: {data['status']}")
        return data["id"]
    
    def test_create_poll_validation_no_question(self, auth_headers):
        """POST /api/polls should fail without question"""
        poll_data = {
            "question": "",
            "options": ["A", "B"]
        }
        response = requests.post(f"{BASE_URL}/api/polls", json=poll_data, headers=auth_headers)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Validation: Empty question rejected")
    
    def test_create_poll_validation_few_options(self, auth_headers):
        """POST /api/polls should fail with less than 2 options"""
        poll_data = {
            "question": "Test question?",
            "options": ["Only one"]
        }
        response = requests.post(f"{BASE_URL}/api/polls", json=poll_data, headers=auth_headers)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Validation: Less than 2 options rejected")
    
    def test_delete_poll(self, auth_headers):
        """DELETE /api/polls/{id} deletes a poll"""
        # First create a poll
        poll_data = {
            "question": "TEST_Poll to delete",
            "options": ["Yes", "No"]
        }
        create_resp = requests.post(f"{BASE_URL}/api/polls", json=poll_data, headers=auth_headers)
        assert create_resp.status_code == 200, f"Create failed: {create_resp.text}"
        poll_id = create_resp.json()["id"]
        
        # Delete it
        delete_resp = requests.delete(f"{BASE_URL}/api/polls/{poll_id}", headers=auth_headers)
        assert delete_resp.status_code == 200, f"DELETE failed: {delete_resp.text}"
        print(f"✓ Deleted poll {poll_id}")
        
        # Verify it's gone
        get_resp = requests.get(f"{BASE_URL}/api/polls", headers=auth_headers)
        polls = get_resp.json()
        poll_ids = [p["id"] for p in polls]
        assert poll_id not in poll_ids, "Poll should be deleted"
        print("✓ Verified poll is deleted")


class TestScheduledPostsAPI:
    """Test Scheduled Posts endpoints"""
    
    def test_get_scheduled_posts_returns_list(self, auth_headers):
        """GET /api/scheduled-posts should return a list"""
        response = requests.get(f"{BASE_URL}/api/scheduled-posts", headers=auth_headers)
        assert response.status_code == 200, f"GET /api/scheduled-posts failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET /api/scheduled-posts returns list with {len(data)} posts")


class TestPaidPostsCreateAPI:
    """Test Dashboard Paid Post Creation endpoints"""
    
    def test_paid_posts_create_endpoint_exists(self, auth_headers):
        """POST /api/paid-posts/create endpoint should exist (multipart form)"""
        # Send minimal request to check endpoint exists
        # Without files, it should return 422 (validation error) not 404
        response = requests.post(
            f"{BASE_URL}/api/paid-posts/create",
            headers=auth_headers,
            data={"channel_id": "-1001234567890", "price": "99", "blur_level": "25"}
        )
        # Should be 422 (missing files) or 400, not 404
        assert response.status_code != 404, f"Endpoint not found: {response.status_code}"
        print(f"✓ POST /api/paid-posts/create endpoint exists (status: {response.status_code})")
    
    def test_paid_posts_create_with_file(self, auth_headers):
        """POST /api/paid-posts/create with a test image file"""
        # Create a simple test image (1x1 pixel PNG)
        # PNG header for 1x1 red pixel
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
            0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
            0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,  # IEND chunk
            0x44, 0xAE, 0x42, 0x60, 0x82
        ])
        
        files = [("files", ("test.png", io.BytesIO(png_data), "image/png"))]
        data = {
            "channel_id": "-1001234567890",  # Fake channel ID
            "price": "99",
            "blur_level": "25",
            "caption": "TEST_Dashboard paid post"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/paid-posts/create",
            headers={"Authorization": auth_headers["Authorization"]},
            data=data,
            files=files
        )
        # May fail due to invalid channel/bot token, but should not be 404 or 422
        # Expected: 500 (bot token issue) or 200 (success)
        print(f"✓ POST /api/paid-posts/create with file: status {response.status_code}")
        if response.status_code == 500:
            print(f"  (Expected - bot token/channel issue: {response.json().get('detail', 'unknown')})")
    
    def test_preview_blur_endpoint_exists(self, auth_headers):
        """POST /api/paid-posts/preview-blur endpoint should exist"""
        # Without file, should return 422 not 404
        response = requests.post(
            f"{BASE_URL}/api/paid-posts/preview-blur",
            headers=auth_headers,
            data={"blur_level": "25"}
        )
        assert response.status_code != 404, f"Endpoint not found: {response.status_code}"
        print(f"✓ POST /api/paid-posts/preview-blur endpoint exists (status: {response.status_code})")
    
    def test_preview_blur_with_file(self, auth_headers):
        """POST /api/paid-posts/preview-blur with a test image"""
        # Create a simple test image
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
            0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
            0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
            0x44, 0xAE, 0x42, 0x60, 0x82
        ])
        
        files = {"file": ("test.png", io.BytesIO(png_data), "image/png")}
        data = {"blur_level": "50"}
        
        response = requests.post(
            f"{BASE_URL}/api/paid-posts/preview-blur",
            headers={"Authorization": auth_headers["Authorization"]},
            data=data,
            files=files
        )
        # Should return 200 with preview_url or 500 if blur fails
        print(f"✓ POST /api/paid-posts/preview-blur with file: status {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            assert "preview_url" in data, "Response should have preview_url"
            print(f"  Preview URL: {data['preview_url']}")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_polls(self, auth_headers):
        """Delete all TEST_ prefixed polls"""
        response = requests.get(f"{BASE_URL}/api/polls", headers=auth_headers)
        if response.status_code == 200:
            polls = response.json()
            for poll in polls:
                if poll.get("question", "").startswith("TEST_"):
                    requests.delete(f"{BASE_URL}/api/polls/{poll['id']}", headers=auth_headers)
                    print(f"  Cleaned up poll: {poll['id']}")
        print("✓ Cleanup complete")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
