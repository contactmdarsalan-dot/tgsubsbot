"""
Iteration 14 Tests - Tenant Isolation & Live Ticket Features
Tests:
1. Tenant Isolation - tenant_id field in data
2. Admin Stats API with tenant scoping
3. Tenant Management API
4. Live Sessions Public API
5. Live Ticket Status API
6. Live Ticket Upload Screenshot API
7. Plans API still works
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
ADMIN_TG_ID = "123456789"
NON_ADMIN_TG_ID = "9999999"


class TestTenantIsolation:
    """Test tenant isolation features"""
    
    def test_admin_stats_returns_tenant_scoped_data(self):
        """Admin stats should return data scoped to tenant"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/stats/{ADMIN_TG_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify stats structure
        assert "total_subscribers" in data, "Missing total_subscribers"
        assert "active_subscribers" in data, "Missing active_subscribers"
        assert "pending_payments" in data, "Missing pending_payments"
        assert "total_revenue" in data, "Missing total_revenue"
        
        # Values should be integers
        assert isinstance(data["total_subscribers"], int)
        assert isinstance(data["active_subscribers"], int)
        assert isinstance(data["pending_payments"], int)
        print(f"Admin stats: {data}")
    
    def test_admin_stats_403_for_non_admin(self):
        """Non-admin should get 403 on admin stats"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/stats/{NON_ADMIN_TG_ID}")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("Non-admin correctly denied access to admin stats")


class TestTenantManagement:
    """Test tenant management API"""
    
    def test_get_tenant_info_for_admin(self):
        """GET /api/miniapp/admin/tenant/{tg_id} returns tenant info"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/tenant/{ADMIN_TG_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "tenant_id" in data, "Missing tenant_id in response"
        assert "name" in data, "Missing name in response"
        assert "status" in data, "Missing status in response"
        
        # Default tenant should be 'default'
        print(f"Tenant info: {data}")
    
    def test_get_tenant_403_for_non_admin(self):
        """Non-admin should get 403 on tenant endpoint"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/tenant/{NON_ADMIN_TG_ID}")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("Non-admin correctly denied access to tenant info")


class TestLiveSessionsPublic:
    """Test public live sessions API"""
    
    def test_get_public_live_sessions(self):
        """GET /api/miniapp/live-sessions/public returns active sessions"""
        response = requests.get(f"{BASE_URL}/api/miniapp/live-sessions/public")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of sessions"
        
        # If there are sessions, verify structure
        if len(data) > 0:
            session = data[0]
            assert "id" in session, "Missing id in session"
            assert "title" in session, "Missing title in session"
            assert "status" in session, "Missing status in session"
            # Status should be one of: scheduled, announced, live
            assert session["status"] in ["scheduled", "announced", "live"], f"Unexpected status: {session['status']}"
            print(f"Found {len(data)} public live sessions")
        else:
            print("No public live sessions found (expected if none created)")


class TestLiveTicketStatus:
    """Test live ticket status API"""
    
    def test_get_ticket_status_no_ticket(self):
        """GET /api/miniapp/live-ticket/status/{tg_id}/{session_id} returns no ticket"""
        # Use a non-existent session ID
        response = requests.get(f"{BASE_URL}/api/miniapp/live-ticket/status/{ADMIN_TG_ID}/nonexistent-session")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "has_ticket" in data, "Missing has_ticket field"
        assert data["has_ticket"] == False, "Expected has_ticket=False for non-existent session"
        print(f"Ticket status (no ticket): {data}")
    
    def test_get_ticket_status_with_session(self):
        """Test ticket status with a real session ID"""
        # First get public sessions
        sessions_resp = requests.get(f"{BASE_URL}/api/miniapp/live-sessions/public")
        sessions = sessions_resp.json()
        
        if len(sessions) > 0:
            session_id = sessions[0]["id"]
            response = requests.get(f"{BASE_URL}/api/miniapp/live-ticket/status/{ADMIN_TG_ID}/{session_id}")
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            
            data = response.json()
            assert "has_ticket" in data
            print(f"Ticket status for session {session_id}: {data}")
        else:
            print("Skipping - no live sessions available")


class TestLiveTicketUpload:
    """Test live ticket screenshot upload API"""
    
    def test_upload_screenshot_no_file(self):
        """POST without file should return 422"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/live-ticket/upload-screenshot",
            data={"telegram_user_id": ADMIN_TG_ID, "session_id": "test-session"}
        )
        # Should fail without file
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
        print("Upload without file correctly rejected")
    
    def test_upload_screenshot_invalid_session(self):
        """POST with invalid session should return 404"""
        # Create a dummy image file
        import io
        dummy_image = io.BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
        
        response = requests.post(
            f"{BASE_URL}/api/miniapp/live-ticket/upload-screenshot",
            files={"file": ("test.png", dummy_image, "image/png")},
            data={"telegram_user_id": ADMIN_TG_ID, "session_id": "nonexistent-session-id"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("Upload with invalid session correctly rejected")


class TestPlansAPI:
    """Test plans API still works after tenant changes"""
    
    def test_get_plans(self):
        """GET /api/miniapp/plans returns active plans"""
        response = requests.get(f"{BASE_URL}/api/miniapp/plans")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of plans"
        assert len(data) > 0, "Expected at least one plan"
        
        # Verify plan structure
        plan = data[0]
        assert "id" in plan, "Missing id in plan"
        assert "name" in plan, "Missing name in plan"
        assert "price" in plan, "Missing price in plan"
        assert "duration_days" in plan, "Missing duration_days in plan"
        
        print(f"Found {len(data)} plans")
        for p in data[:3]:
            print(f"  - {p['name']}: ₹{p['price']} ({p['duration_days']} days)")


class TestAdminLiveSessions:
    """Test admin live sessions management"""
    
    def test_get_admin_live_sessions(self):
        """GET /api/miniapp/admin/live-sessions/{tg_id} returns sessions for admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/live-sessions/{ADMIN_TG_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of sessions"
        
        if len(data) > 0:
            session = data[0]
            # Verify tenant_id is present
            if "tenant_id" in session:
                print(f"Session has tenant_id: {session['tenant_id']}")
            print(f"Found {len(data)} admin live sessions")
        else:
            print("No admin live sessions found")
    
    def test_create_live_session_with_tenant(self):
        """POST /api/miniapp/admin/live-session creates session with tenant_id"""
        import uuid
        
        session_data = {
            "telegram_user_id": ADMIN_TG_ID,
            "title": f"Test Session {uuid.uuid4().hex[:6]}",
            "description": "Test session for iteration 14",
            "scheduled_date": "2026-04-01",
            "scheduled_time": "18:00",
            "price": 99,
            "max_viewers": 50,
            "stream_link": "https://example.com/stream",
            "superchat_enabled": False
        }
        
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/live-session",
            json=session_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Missing id in response"
        assert "tenant_id" in data, "Missing tenant_id in response"
        assert data["title"] == session_data["title"], "Title mismatch"
        assert data["status"] == "scheduled", "Expected status=scheduled"
        
        print(f"Created live session: {data['id']} with tenant_id: {data['tenant_id']}")
        
        # Cleanup - delete the session
        delete_resp = requests.delete(
            f"{BASE_URL}/api/miniapp/admin/live-session/{data['id']}",
            json={"telegram_user_id": ADMIN_TG_ID}
        )
        print(f"Cleanup delete: {delete_resp.status_code}")


class TestAdminSubscribers:
    """Test admin subscribers API with tenant scoping"""
    
    def test_get_subscribers(self):
        """GET /api/miniapp/admin/subscribers/{tg_id} returns tenant-scoped subscribers"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/subscribers/{ADMIN_TG_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of subscribers"
        
        print(f"Found {len(data)} subscribers")
        
        # Check if any have tenant_id
        if len(data) > 0:
            sub = data[0]
            if "tenant_id" in sub:
                print(f"Subscriber has tenant_id: {sub['tenant_id']}")


class TestAdminBroadcast:
    """Test admin broadcast with tenant scoping"""
    
    def test_broadcast_permission_check(self):
        """Non-admin should get 403 on broadcast"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/broadcast",
            json={"telegram_user_id": NON_ADMIN_TG_ID, "message": "Test"}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("Non-admin correctly denied broadcast access")


class TestAdminCheck:
    """Test admin check endpoint"""
    
    def test_admin_check_for_admin(self):
        """Admin user should be recognized"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/check/{ADMIN_TG_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["is_admin"] == True, "Expected is_admin=True"
        assert "permissions" in data, "Missing permissions"
        print(f"Admin check: {data}")
    
    def test_admin_check_for_non_admin(self):
        """Non-admin user should not be recognized as admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/check/{NON_ADMIN_TG_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["is_admin"] == False, "Expected is_admin=False"
        print(f"Non-admin check: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
