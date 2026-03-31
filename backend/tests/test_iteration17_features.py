"""
Iteration 17 Backend Tests
Features to test:
1. Plans tab shows 'Extend Subscription' title when user has active subscription
2. Plans tab shows expiry warning banner when subscription has 3 or fewer days remaining
3. Plans tab shows blue extend banner with plan name and days remaining when subscription is active
4. Payment button text changes to 'Extend - Pay ₹X' when subscription active
5. Extension note shows '+X days will be added' when purchasing with active subscription
6. Admin Live tab shows all sessions with proper status badges (SCHEDULED, ANNOUNCED, LIVE, ENDED)
7. Scheduled sessions show Announce + Go Live + Delete buttons
8. POST /api/miniapp/admin/live-session/{id}/end endpoint ends a live session
9. DELETE /api/miniapp/admin/live-session/{id} endpoint deletes session
10. Live sessions show description text and metadata (stream link, superchat, tickets)
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test admin TG ID
ADMIN_TG_ID = "123456789"
NON_ADMIN_TG_ID = "9999999"


class TestSubscriptionStatus:
    """Test subscription status endpoint for extend subscription UI logic"""
    
    def test_get_subscription_status_active(self):
        """Test getting subscription status for a user"""
        response = requests.get(f"{BASE_URL}/api/miniapp/status/{ADMIN_TG_ID}")
        assert response.status_code == 200
        data = response.json()
        # Response should have is_active, plan_name, days_remaining fields
        assert "is_active" in data
        if data["is_active"]:
            assert "plan_name" in data
            assert "days_remaining" in data
            assert "end_date" in data
            print(f"Active subscription: {data['plan_name']}, {data['days_remaining']} days remaining")
        else:
            print("No active subscription for this user")
    
    def test_get_subscription_status_non_existent_user(self):
        """Test getting subscription status for non-existent user"""
        response = requests.get(f"{BASE_URL}/api/miniapp/status/nonexistent123")
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] == False
        print("Non-existent user correctly returns is_active=False")


class TestPlansEndpoint:
    """Test plans endpoint for extend subscription UI"""
    
    def test_get_plans(self):
        """Test getting available plans"""
        response = requests.get(f"{BASE_URL}/api/miniapp/plans")
        assert response.status_code == 200
        plans = response.json()
        assert isinstance(plans, list)
        if plans:
            plan = plans[0]
            assert "id" in plan
            assert "name" in plan
            assert "price" in plan
            assert "duration_days" in plan
            print(f"Found {len(plans)} plans. First plan: {plan['name']} - ₹{plan['price']} for {plan['duration_days']} days")
        else:
            print("No plans found")


class TestAdminLiveSessions:
    """Test Admin Live Session management endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.test_session_id = None
    
    def test_admin_check(self):
        """Verify admin check endpoint works"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/check/{ADMIN_TG_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["is_admin"] == True
        assert "permissions" in data
        print(f"Admin verified: {data.get('name', 'Admin')}, permissions: {data.get('permissions', [])}")
    
    def test_get_admin_live_sessions(self):
        """Test getting live sessions for admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/live-sessions/{ADMIN_TG_ID}")
        assert response.status_code == 200
        sessions = response.json()
        assert isinstance(sessions, list)
        print(f"Found {len(sessions)} live sessions")
        
        # Check session structure if any exist
        for session in sessions[:3]:  # Check first 3
            assert "id" in session
            assert "title" in session
            assert "status" in session
            # Status should be one of: scheduled, announced, live, ended
            assert session["status"] in ["scheduled", "announced", "live", "ended"]
            print(f"  - {session['title']}: {session['status']}")
    
    def test_create_live_session(self):
        """Test creating a new live session"""
        payload = {
            "telegram_user_id": ADMIN_TG_ID,
            "title": "TEST_Iteration17_Live_Session",
            "description": "Test description for iteration 17",
            "scheduled_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
            "scheduled_time": "18:00",
            "price": 99,
            "stream_link": "https://youtube.com/test",
            "max_viewers": 50,
            "superchat_enabled": True,
            "superchat_min_amount": 25
        }
        response = requests.post(f"{BASE_URL}/api/miniapp/admin/live-session", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert data["title"] == "TEST_Iteration17_Live_Session"
        assert data["description"] == "Test description for iteration 17"
        assert data["status"] == "scheduled"
        assert data["price"] == 99
        assert data["stream_link"] == "https://youtube.com/test"
        assert data["superchat_enabled"] == True
        assert data["superchat_min_amount"] == 25
        
        self.__class__.test_session_id = data["id"]
        print(f"Created live session: {data['id']}")
        return data["id"]
    
    def test_end_live_session(self):
        """Test POST /api/miniapp/admin/live-session/{id}/end endpoint"""
        # First create a session
        create_payload = {
            "telegram_user_id": ADMIN_TG_ID,
            "title": "TEST_End_Session_Test",
            "description": "Session to test end endpoint",
            "scheduled_date": datetime.now().strftime("%Y-%m-%d"),
            "scheduled_time": "12:00",
            "price": 0
        }
        create_response = requests.post(f"{BASE_URL}/api/miniapp/admin/live-session", json=create_payload)
        assert create_response.status_code == 200
        session_id = create_response.json()["id"]
        
        # Go live first
        go_live_response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/live-session/{session_id}/go-live",
            json={"telegram_user_id": ADMIN_TG_ID}
        )
        assert go_live_response.status_code == 200
        
        # Now end the session
        end_response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/live-session/{session_id}/end",
            json={"telegram_user_id": ADMIN_TG_ID}
        )
        assert end_response.status_code == 200
        data = end_response.json()
        assert data["success"] == True
        assert data["status"] == "ended"
        print(f"Successfully ended live session: {session_id}")
        
        # Verify session status changed
        sessions_response = requests.get(f"{BASE_URL}/api/miniapp/admin/live-sessions/{ADMIN_TG_ID}")
        sessions = sessions_response.json()
        ended_session = next((s for s in sessions if s["id"] == session_id), None)
        assert ended_session is not None
        assert ended_session["status"] == "ended"
        print(f"Verified session status is 'ended'")
        
        # Cleanup - delete the session
        requests.delete(
            f"{BASE_URL}/api/miniapp/admin/live-session/{session_id}",
            json={"telegram_user_id": ADMIN_TG_ID}
        )
    
    def test_delete_live_session(self):
        """Test DELETE /api/miniapp/admin/live-session/{id} endpoint"""
        # First create a session to delete
        create_payload = {
            "telegram_user_id": ADMIN_TG_ID,
            "title": "TEST_Delete_Session_Test",
            "description": "Session to test delete endpoint",
            "scheduled_date": datetime.now().strftime("%Y-%m-%d"),
            "scheduled_time": "14:00",
            "price": 0
        }
        create_response = requests.post(f"{BASE_URL}/api/miniapp/admin/live-session", json=create_payload)
        assert create_response.status_code == 200
        session_id = create_response.json()["id"]
        print(f"Created session to delete: {session_id}")
        
        # Delete the session
        delete_response = requests.delete(
            f"{BASE_URL}/api/miniapp/admin/live-session/{session_id}",
            json={"telegram_user_id": ADMIN_TG_ID}
        )
        assert delete_response.status_code == 200
        data = delete_response.json()
        assert data["success"] == True
        print(f"Successfully deleted live session: {session_id}")
        
        # Verify session is deleted
        sessions_response = requests.get(f"{BASE_URL}/api/miniapp/admin/live-sessions/{ADMIN_TG_ID}")
        sessions = sessions_response.json()
        deleted_session = next((s for s in sessions if s["id"] == session_id), None)
        assert deleted_session is None
        print(f"Verified session is deleted from list")
    
    def test_live_session_status_transitions(self):
        """Test live session status transitions: scheduled -> announced -> live -> ended"""
        # Create session
        create_payload = {
            "telegram_user_id": ADMIN_TG_ID,
            "title": "TEST_Status_Transition_Test",
            "description": "Testing status transitions",
            "scheduled_date": datetime.now().strftime("%Y-%m-%d"),
            "scheduled_time": "16:00",
            "price": 50
        }
        create_response = requests.post(f"{BASE_URL}/api/miniapp/admin/live-session", json=create_payload)
        assert create_response.status_code == 200
        session_id = create_response.json()["id"]
        assert create_response.json()["status"] == "scheduled"
        print(f"Created session with status: scheduled")
        
        # Announce
        announce_response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/announce-live/{session_id}",
            json={"telegram_user_id": ADMIN_TG_ID}
        )
        assert announce_response.status_code == 200
        print(f"Announced session, status should be: announced")
        
        # Go Live
        go_live_response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/live-session/{session_id}/go-live",
            json={"telegram_user_id": ADMIN_TG_ID}
        )
        assert go_live_response.status_code == 200
        assert go_live_response.json()["status"] == "live"
        print(f"Session is now: live")
        
        # End
        end_response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/live-session/{session_id}/end",
            json={"telegram_user_id": ADMIN_TG_ID}
        )
        assert end_response.status_code == 200
        assert end_response.json()["status"] == "ended"
        print(f"Session ended, status: ended")
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/miniapp/admin/live-session/{session_id}",
            json={"telegram_user_id": ADMIN_TG_ID}
        )
        print("Cleanup complete")
    
    def test_non_admin_cannot_access_live_sessions(self):
        """Test that non-admin cannot access live sessions"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/live-sessions/{NON_ADMIN_TG_ID}")
        assert response.status_code == 403
        print("Non-admin correctly denied access to live sessions")
    
    def test_non_admin_cannot_end_session(self):
        """Test that non-admin cannot end a live session"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/live-session/fake-id/end",
            json={"telegram_user_id": NON_ADMIN_TG_ID}
        )
        assert response.status_code == 403
        print("Non-admin correctly denied from ending session")
    
    def test_non_admin_cannot_delete_session(self):
        """Test that non-admin cannot delete a live session"""
        response = requests.delete(
            f"{BASE_URL}/api/miniapp/admin/live-session/fake-id",
            json={"telegram_user_id": NON_ADMIN_TG_ID}
        )
        assert response.status_code == 403
        print("Non-admin correctly denied from deleting session")


class TestPublicLiveSessions:
    """Test public live sessions endpoint"""
    
    def test_get_public_live_sessions(self):
        """Test getting public live sessions (no auth required)"""
        response = requests.get(f"{BASE_URL}/api/miniapp/live-sessions/public")
        assert response.status_code == 200
        sessions = response.json()
        assert isinstance(sessions, list)
        print(f"Found {len(sessions)} public live sessions")
        
        # All sessions should be scheduled, announced, or live (not ended)
        for session in sessions:
            assert session["status"] in ["scheduled", "announced", "live"]
            print(f"  - {session['title']}: {session['status']}")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_sessions(self):
        """Delete all TEST_ prefixed sessions"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/live-sessions/{ADMIN_TG_ID}")
        if response.status_code == 200:
            sessions = response.json()
            for session in sessions:
                if session.get("title", "").startswith("TEST_"):
                    requests.delete(
                        f"{BASE_URL}/api/miniapp/admin/live-session/{session['id']}",
                        json={"telegram_user_id": ADMIN_TG_ID}
                    )
                    print(f"Cleaned up: {session['title']}")
        print("Cleanup complete")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
