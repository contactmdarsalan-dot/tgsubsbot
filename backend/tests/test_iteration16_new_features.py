"""
Iteration 16 Backend Tests - New Features:
1. Landing Page at / (frontend only)
2. Admin Panel Live tab always visible
3. Paid Posts form with media upload
4. POST /api/miniapp/admin/paid-post-with-media endpoint
5. POST /api/miniapp/admin/paid-post endpoint (text posts)
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPaidPostsAPI:
    """Test Paid Posts endpoints"""
    
    def test_admin_check_returns_admin_status(self):
        """Test admin check endpoint returns admin status"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/check/123456789")
        assert response.status_code == 200
        data = response.json()
        assert "is_admin" in data
        assert data["is_admin"] == True
        assert "permissions" in data
        assert "name" in data
        print(f"✅ Admin check: is_admin={data['is_admin']}, name={data['name']}")
    
    def test_admin_check_non_admin(self):
        """Test admin check for non-admin user"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/check/9999999")
        assert response.status_code == 200
        data = response.json()
        assert data["is_admin"] == False
        print(f"✅ Non-admin check: is_admin={data['is_admin']}")
    
    def test_create_text_paid_post(self):
        """Test creating a text-only paid post"""
        payload = {
            "telegram_user_id": "123456789",
            "caption": "TEST_Text Post Caption",
            "price": 99,
            "blur_level": 15,
            "content_type": "text",
            "channel_id": ""
        }
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/paid-post",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["caption"] == "TEST_Text Post Caption"
        assert data["price"] == 99
        assert data["content_type"] == "text"
        assert data["is_active"] == True
        print(f"✅ Created text paid post: id={data['id']}, caption={data['caption']}")
        return data["id"]
    
    def test_create_paid_post_with_media(self):
        """Test creating a paid post with media upload"""
        # Create a simple test image (1x1 pixel PNG)
        test_image = io.BytesIO()
        # Minimal PNG file
        test_image.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82')
        test_image.seek(0)
        
        files = {
            'file': ('test_image.png', test_image, 'image/png')
        }
        data = {
            'telegram_user_id': '123456789',
            'caption': 'TEST_Photo Post Caption',
            'price': 199,
            'blur_level': 20,
            'content_type': 'photo',
            'channel_id': ''
        }
        
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/paid-post-with-media",
            files=files,
            data=data
        )
        assert response.status_code == 200
        result = response.json()
        assert "id" in result
        assert result["caption"] == "TEST_Photo Post Caption"
        assert result["price"] == 199
        assert result["content_type"] == "photo"
        assert "media_url" in result
        assert result["media_url"].startswith("/api/uploads/")
        print(f"✅ Created photo paid post: id={result['id']}, media_url={result['media_url']}")
        return result["id"]
    
    def test_get_paid_posts_list(self):
        """Test getting list of paid posts"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/paid-posts/123456789")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Got paid posts list: {len(data)} posts")
    
    def test_toggle_paid_post(self):
        """Test toggling paid post active status"""
        # First create a post
        payload = {
            "telegram_user_id": "123456789",
            "caption": "TEST_Toggle Post",
            "price": 50,
            "content_type": "text"
        }
        create_response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/paid-post",
            json=payload
        )
        assert create_response.status_code == 200
        post_id = create_response.json()["id"]
        
        # Toggle it off
        toggle_response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/paid-post/{post_id}/toggle",
            json={"telegram_user_id": "123456789"}
        )
        assert toggle_response.status_code == 200
        toggle_data = toggle_response.json()
        assert toggle_data["success"] == True
        assert toggle_data["is_active"] == False
        print(f"✅ Toggled post {post_id} to inactive")
        
        # Toggle it back on
        toggle_response2 = requests.post(
            f"{BASE_URL}/api/miniapp/admin/paid-post/{post_id}/toggle",
            json={"telegram_user_id": "123456789"}
        )
        assert toggle_response2.status_code == 200
        assert toggle_response2.json()["is_active"] == True
        print(f"✅ Toggled post {post_id} back to active")
    
    def test_update_blur_level(self):
        """Test updating blur level for a paid post"""
        # First create a post
        payload = {
            "telegram_user_id": "123456789",
            "caption": "TEST_Blur Post",
            "price": 75,
            "blur_level": 10,
            "content_type": "text"
        }
        create_response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/paid-post",
            json=payload
        )
        assert create_response.status_code == 200
        post_id = create_response.json()["id"]
        
        # Update blur level
        blur_response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/paid-post/{post_id}/blur",
            json={"telegram_user_id": "123456789", "blur_level": 35}
        )
        assert blur_response.status_code == 200
        blur_data = blur_response.json()
        assert blur_data["success"] == True
        assert blur_data["blur_level"] == 35
        print(f"✅ Updated blur level for post {post_id} to 35")
    
    def test_paid_post_non_admin_forbidden(self):
        """Test that non-admin cannot create paid posts"""
        payload = {
            "telegram_user_id": "9999999",  # Non-admin user
            "caption": "Should Fail",
            "price": 100,
            "content_type": "text"
        }
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/paid-post",
            json=payload
        )
        assert response.status_code == 403
        print("✅ Non-admin correctly forbidden from creating paid posts")


class TestLiveSessionsAPI:
    """Test Live Sessions endpoints (Live tab always visible)"""
    
    def test_get_live_sessions_admin(self):
        """Test getting live sessions for admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/live-sessions/123456789")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Got admin live sessions: {len(data)} sessions")
    
    def test_get_public_live_sessions(self):
        """Test getting public live sessions"""
        response = requests.get(f"{BASE_URL}/api/miniapp/live-sessions/public")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Got public live sessions: {len(data)} sessions")
    
    def test_create_live_session(self):
        """Test creating a live session"""
        payload = {
            "telegram_user_id": "123456789",
            "title": "TEST_Live Session",
            "description": "Test description",
            "scheduled_date": "2026-04-15",
            "scheduled_time": "20:00",
            "price": 149,
            "max_viewers": 50,
            "stream_link": "https://example.com/stream"
        }
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/live-session",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["title"] == "TEST_Live Session"
        assert data["price"] == 149
        assert data["status"] == "scheduled"
        print(f"✅ Created live session: id={data['id']}, title={data['title']}")
        return data["id"]


class TestAdminStatsAPI:
    """Test Admin Stats endpoints"""
    
    def test_get_admin_stats(self):
        """Test getting admin stats"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/stats/123456789")
        assert response.status_code == 200
        data = response.json()
        assert "total_subscribers" in data
        assert "active_subscribers" in data
        assert "pending_payments" in data
        assert "total_revenue" in data
        print(f"✅ Admin stats: revenue={data['total_revenue']}, active_subs={data['active_subscribers']}")
    
    def test_get_admin_subscribers(self):
        """Test getting admin subscribers list"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/subscribers/123456789")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ Got subscribers list: {len(data)} subscribers")


class TestMiniAppPlansAPI:
    """Test MiniApp Plans endpoints"""
    
    def test_get_plans(self):
        """Test getting plans"""
        response = requests.get(f"{BASE_URL}/api/miniapp/plans")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Verify plan structure
        plan = data[0]
        assert "id" in plan
        assert "name" in plan
        assert "price" in plan
        assert "duration_days" in plan
        print(f"✅ Got plans: {len(data)} plans")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
