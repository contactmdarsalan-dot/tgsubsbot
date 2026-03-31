"""
Iteration 13 Tests - Mini App Admin Panel Enhancements
Tests for:
1. Paid Posts CRUD endpoints
2. Go Live functionality
3. Admin check endpoint
4. Non-admin access restrictions
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_TG_ID = "123456789"
NON_ADMIN_TG_ID = "9999999"


class TestPaidPostsEndpoints:
    """Test Paid Posts CRUD operations"""
    
    def test_get_paid_posts_as_admin(self):
        """GET /api/miniapp/admin/paid-posts/{telegram_user_id} returns list for admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/paid-posts/{ADMIN_TG_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of paid posts"
        print(f"PASS: GET paid-posts returns {len(data)} posts")
    
    def test_get_paid_posts_as_non_admin(self):
        """GET /api/miniapp/admin/paid-posts/{telegram_user_id} returns 403 for non-admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/paid-posts/{NON_ADMIN_TG_ID}")
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}"
        print("PASS: Non-admin cannot access paid posts")
    
    def test_create_paid_post(self):
        """POST /api/miniapp/admin/paid-post creates new paid post"""
        payload = {
            "telegram_user_id": ADMIN_TG_ID,
            "caption": "Test Paid Post from Iteration 13",
            "price": 99
        }
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/paid-post",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data, "Response should contain post id"
        assert data.get("caption") == payload["caption"], "Caption should match"
        assert data.get("price") == payload["price"], "Price should match"
        assert data.get("is_active") == True, "New post should be active"
        print(f"PASS: Created paid post with id={data['id']}")
        return data["id"]
    
    def test_toggle_paid_post(self):
        """POST /api/miniapp/admin/paid-post/{post_id}/toggle toggles is_active status"""
        # First create a post
        create_payload = {
            "telegram_user_id": ADMIN_TG_ID,
            "caption": "Toggle Test Post",
            "price": 50
        }
        create_response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/paid-post",
            json=create_payload
        )
        assert create_response.status_code == 200
        post_id = create_response.json()["id"]
        
        # Toggle it (should become inactive)
        toggle_response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/paid-post/{post_id}/toggle",
            json={"telegram_user_id": ADMIN_TG_ID}
        )
        assert toggle_response.status_code == 200, f"Expected 200, got {toggle_response.status_code}"
        toggle_data = toggle_response.json()
        assert toggle_data.get("success") == True, "Toggle should succeed"
        assert toggle_data.get("is_active") == False, "Post should now be inactive"
        print(f"PASS: Toggled post {post_id} to inactive")
        
        # Toggle again (should become active)
        toggle_response2 = requests.post(
            f"{BASE_URL}/api/miniapp/admin/paid-post/{post_id}/toggle",
            json={"telegram_user_id": ADMIN_TG_ID}
        )
        assert toggle_response2.status_code == 200
        assert toggle_response2.json().get("is_active") == True, "Post should now be active again"
        print(f"PASS: Toggled post {post_id} back to active")


class TestGoLiveEndpoint:
    """Test Go Live functionality"""
    
    def test_create_live_session(self):
        """POST /api/miniapp/admin/live-session creates a live session"""
        payload = {
            "telegram_user_id": ADMIN_TG_ID,
            "title": "Test Live Session",
            "description": "Testing go live feature",
            "scheduled_date": "2026-01-20",
            "scheduled_time": "18:00",
            "price": 0,
            "stream_link": "https://example.com/stream"
        }
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/live-session",
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data, "Response should contain session id"
        assert data.get("status") == "scheduled", "New session should be scheduled"
        print(f"PASS: Created live session with id={data['id']}")
        return data["id"]
    
    def test_go_live(self):
        """POST /api/miniapp/admin/live-session/{session_id}/go-live marks session as live"""
        # First create a session
        create_payload = {
            "telegram_user_id": ADMIN_TG_ID,
            "title": "Go Live Test Session",
            "scheduled_date": "2026-01-20",
            "scheduled_time": "19:00"
        }
        create_response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/live-session",
            json=create_payload
        )
        assert create_response.status_code == 200
        session_id = create_response.json()["id"]
        
        # Go live
        go_live_response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/live-session/{session_id}/go-live",
            json={"telegram_user_id": ADMIN_TG_ID}
        )
        assert go_live_response.status_code == 200, f"Expected 200, got {go_live_response.status_code}"
        data = go_live_response.json()
        assert data.get("success") == True, "Go live should succeed"
        assert data.get("status") == "live", "Session status should be 'live'"
        print(f"PASS: Session {session_id} is now LIVE")
    
    def test_get_live_sessions(self):
        """GET /api/miniapp/admin/live-sessions/{telegram_user_id} returns sessions"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/live-sessions/{ADMIN_TG_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Expected list of live sessions"
        print(f"PASS: GET live-sessions returns {len(data)} sessions")


class TestAdminCheck:
    """Test admin check endpoint"""
    
    def test_admin_check_for_admin(self):
        """GET /api/miniapp/admin/check/{telegram_user_id} returns is_admin=true for admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/check/{ADMIN_TG_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("is_admin") == True, "Admin should have is_admin=true"
        assert "permissions" in data, "Response should include permissions"
        print(f"PASS: Admin check returns is_admin=true with permissions: {data.get('permissions')}")
    
    def test_admin_check_for_non_admin(self):
        """GET /api/miniapp/admin/check/{telegram_user_id} returns is_admin=false for non-admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/check/{NON_ADMIN_TG_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("is_admin") == False, "Non-admin should have is_admin=false"
        print("PASS: Non-admin check returns is_admin=false")


class TestAdminStats:
    """Test admin stats endpoint"""
    
    def test_admin_stats(self):
        """GET /api/miniapp/admin/stats/{telegram_user_id} returns stats for admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/stats/{ADMIN_TG_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "total_subscribers" in data, "Stats should include total_subscribers"
        assert "active_subscribers" in data, "Stats should include active_subscribers"
        assert "pending_payments" in data, "Stats should include pending_payments"
        assert "total_revenue" in data, "Stats should include total_revenue"
        print(f"PASS: Admin stats: {data}")


class TestBroadcastPaidPost:
    """Test broadcast paid post endpoint"""
    
    def test_broadcast_paid_post(self):
        """POST /api/miniapp/admin/paid-post/{post_id}/broadcast sends to users"""
        # First create an active post
        create_payload = {
            "telegram_user_id": ADMIN_TG_ID,
            "caption": "Broadcast Test Post",
            "price": 25
        }
        create_response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/paid-post",
            json=create_payload
        )
        assert create_response.status_code == 200
        post_id = create_response.json()["id"]
        
        # Broadcast it
        broadcast_response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/paid-post/{post_id}/broadcast",
            json={"telegram_user_id": ADMIN_TG_ID}
        )
        assert broadcast_response.status_code == 200, f"Expected 200, got {broadcast_response.status_code}"
        data = broadcast_response.json()
        assert data.get("success") == True, "Broadcast should succeed"
        assert "sent_to" in data, "Response should include sent_to count"
        print(f"PASS: Broadcast sent to {data.get('sent_to')} users")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
