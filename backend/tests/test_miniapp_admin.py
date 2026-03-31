"""
Test Mini App Admin Panel Endpoints
Tests admin check, stats, pending payments, payment actions, subscribers, broadcast, live sessions
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test admin telegram_user_id (from telegram_admins collection)
ADMIN_USER_ID = "123456789"
NON_ADMIN_USER_ID = "9999999999"


class TestAdminCheck:
    """Test admin check endpoint"""
    
    def test_admin_check_returns_is_admin_true_for_admin(self):
        """GET /api/miniapp/admin/check/123456789 returns is_admin=true with permissions"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/check/{ADMIN_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("is_admin") == True, f"Expected is_admin=True, got {data}"
        assert "permissions" in data, "Response should contain permissions"
        assert isinstance(data["permissions"], list), "Permissions should be a list"
        print(f"✅ Admin check for {ADMIN_USER_ID}: is_admin={data['is_admin']}, permissions={data['permissions']}")
    
    def test_admin_check_returns_is_admin_false_for_non_admin(self):
        """GET /api/miniapp/admin/check/9999999999 returns is_admin=false for non-admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/check/{NON_ADMIN_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("is_admin") == False, f"Expected is_admin=False, got {data}"
        print(f"✅ Admin check for {NON_ADMIN_USER_ID}: is_admin={data['is_admin']}")


class TestAdminStats:
    """Test admin stats endpoint"""
    
    def test_admin_stats_returns_data_for_admin(self):
        """GET /api/miniapp/admin/stats/123456789 returns revenue, subscribers counts, pending payments count"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/stats/{ADMIN_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "total_subscribers" in data, "Response should contain total_subscribers"
        assert "active_subscribers" in data, "Response should contain active_subscribers"
        assert "pending_payments" in data, "Response should contain pending_payments"
        assert "total_revenue" in data, "Response should contain total_revenue"
        
        # Verify types
        assert isinstance(data["total_subscribers"], int), "total_subscribers should be int"
        assert isinstance(data["active_subscribers"], int), "active_subscribers should be int"
        assert isinstance(data["pending_payments"], int), "pending_payments should be int"
        assert isinstance(data["total_revenue"], (int, float)), "total_revenue should be numeric"
        
        print(f"✅ Admin stats: total_subs={data['total_subscribers']}, active={data['active_subscribers']}, pending={data['pending_payments']}, revenue={data['total_revenue']}")
    
    def test_admin_stats_returns_403_for_non_admin(self):
        """GET /api/miniapp/admin/stats/9999999999 returns 403 for non-admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/stats/{NON_ADMIN_USER_ID}")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✅ Admin stats correctly returns 403 for non-admin")


class TestAdminPendingPayments:
    """Test admin pending payments endpoint"""
    
    def test_pending_payments_returns_list_for_admin(self):
        """GET /api/miniapp/admin/pending-payments/123456789 returns list of pending payments"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/pending-payments/{ADMIN_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✅ Pending payments: {len(data)} payments found")
        
        # If there are payments, verify structure
        if len(data) > 0:
            payment = data[0]
            assert "id" in payment or "telegram_user_id" in payment, "Payment should have id or telegram_user_id"
            print(f"   Sample payment: {payment.get('id', 'N/A')}, amount: {payment.get('amount', 'N/A')}")
    
    def test_pending_payments_returns_403_for_non_admin(self):
        """GET /api/miniapp/admin/pending-payments/9999999999 returns 403 for non-admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/pending-payments/{NON_ADMIN_USER_ID}")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✅ Pending payments correctly returns 403 for non-admin")


class TestAdminSubscribers:
    """Test admin subscribers endpoint"""
    
    def test_subscribers_returns_list_for_admin(self):
        """GET /api/miniapp/admin/subscribers/123456789 returns subscribers list"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/subscribers/{ADMIN_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✅ Subscribers: {len(data)} subscribers found")
        
        # If there are subscribers, verify structure
        if len(data) > 0:
            sub = data[0]
            assert "telegram_user_id" in sub or "status" in sub, "Subscriber should have telegram_user_id or status"
            print(f"   Sample subscriber: {sub.get('telegram_username', sub.get('telegram_user_id', 'N/A'))}")
    
    def test_subscribers_returns_403_for_non_admin(self):
        """GET /api/miniapp/admin/subscribers/9999999999 returns 403 for non-admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/subscribers/{NON_ADMIN_USER_ID}")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✅ Subscribers correctly returns 403 for non-admin")


class TestAdminBroadcast:
    """Test admin broadcast endpoint"""
    
    def test_broadcast_sends_message_for_admin(self):
        """POST /api/miniapp/admin/broadcast sends message (telegram_user_id=123456789, message=test)"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/broadcast",
            json={
                "telegram_user_id": ADMIN_USER_ID,
                "message": "Test broadcast from iteration 11 testing"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert "broadcast_id" in data, "Response should contain broadcast_id"
        assert "total_recipients" in data, "Response should contain total_recipients"
        
        print(f"✅ Broadcast sent: broadcast_id={data['broadcast_id']}, recipients={data['total_recipients']}")
    
    def test_broadcast_returns_403_for_non_admin(self):
        """POST /api/miniapp/admin/broadcast returns 403 for non-admin"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/broadcast",
            json={
                "telegram_user_id": NON_ADMIN_USER_ID,
                "message": "Test message"
            }
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✅ Broadcast correctly returns 403 for non-admin")
    
    def test_broadcast_returns_400_for_empty_message(self):
        """POST /api/miniapp/admin/broadcast returns 400 for empty message"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/broadcast",
            json={
                "telegram_user_id": ADMIN_USER_ID,
                "message": ""
            }
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print(f"✅ Broadcast correctly returns 400 for empty message")


class TestAdminLiveSessions:
    """Test admin live sessions endpoints"""
    
    def test_live_sessions_returns_list_for_admin(self):
        """GET /api/miniapp/admin/live-sessions/123456789 returns live sessions list"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/live-sessions/{ADMIN_USER_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✅ Live sessions: {len(data)} sessions found")
    
    def test_create_live_session_for_admin(self):
        """POST /api/miniapp/admin/live-session creates a new live session"""
        test_title = f"Test Live Session {uuid.uuid4().hex[:8]}"
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/live-session",
            json={
                "telegram_user_id": ADMIN_USER_ID,
                "title": test_title,
                "description": "Test description",
                "scheduled_date": "2026-02-01",
                "scheduled_time": "18:00",
                "price": 0,
                "stream_link": "https://example.com/stream"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response should contain session id"
        assert data.get("title") == test_title, f"Expected title={test_title}, got {data.get('title')}"
        assert data.get("status") == "scheduled", f"Expected status=scheduled, got {data.get('status')}"
        
        print(f"✅ Live session created: id={data['id']}, title={data['title']}")
        return data["id"]
    
    def test_create_live_session_returns_403_for_non_admin(self):
        """POST /api/miniapp/admin/live-session returns 403 for non-admin"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/live-session",
            json={
                "telegram_user_id": NON_ADMIN_USER_ID,
                "title": "Test",
                "description": "Test"
            }
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✅ Create live session correctly returns 403 for non-admin")


class TestAdminAnnounceLive:
    """Test admin announce live session endpoint"""
    
    def test_announce_live_session(self):
        """POST /api/miniapp/admin/announce-live/{session_id} announces a live session"""
        # First create a session
        create_response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/live-session",
            json={
                "telegram_user_id": ADMIN_USER_ID,
                "title": f"Announce Test {uuid.uuid4().hex[:8]}",
                "description": "Test for announcement",
                "scheduled_date": "2026-02-15",
                "scheduled_time": "20:00",
                "price": 100
            }
        )
        assert create_response.status_code == 200, f"Failed to create session: {create_response.text}"
        session_id = create_response.json()["id"]
        
        # Now announce it
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/announce-live/{session_id}",
            json={"telegram_user_id": ADMIN_USER_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert "sent_to" in data, "Response should contain sent_to count"
        
        print(f"✅ Live session announced: session_id={session_id}, sent_to={data['sent_to']}")
    
    def test_announce_live_returns_404_for_invalid_session(self):
        """POST /api/miniapp/admin/announce-live/invalid-id returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/announce-live/invalid-session-id-12345",
            json={"telegram_user_id": ADMIN_USER_ID}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print(f"✅ Announce live correctly returns 404 for invalid session")


class TestAdminPaymentAction:
    """Test admin payment action endpoint (approve/reject)"""
    
    def test_payment_action_approve(self):
        """POST /api/miniapp/admin/payment-action with approve action updates payment status to verified"""
        # First check if there are any pending payments
        pending_response = requests.get(f"{BASE_URL}/api/miniapp/admin/pending-payments/{ADMIN_USER_ID}")
        pending_payments = pending_response.json()
        
        if len(pending_payments) == 0:
            print("⚠️ No pending payments to test approve action - skipping")
            pytest.skip("No pending payments available for testing")
        
        payment_id = pending_payments[0]["id"]
        
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/payment-action",
            json={
                "telegram_user_id": ADMIN_USER_ID,
                "payment_id": payment_id,
                "action": "approve"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert data.get("new_status") == "verified", f"Expected new_status=verified, got {data.get('new_status')}"
        
        print(f"✅ Payment approved: payment_id={payment_id}, new_status={data['new_status']}")
    
    def test_payment_action_reject(self):
        """POST /api/miniapp/admin/payment-action with reject action updates payment status to rejected"""
        # First check if there are any pending payments
        pending_response = requests.get(f"{BASE_URL}/api/miniapp/admin/pending-payments/{ADMIN_USER_ID}")
        pending_payments = pending_response.json()
        
        if len(pending_payments) == 0:
            print("⚠️ No pending payments to test reject action - skipping")
            pytest.skip("No pending payments available for testing")
        
        payment_id = pending_payments[0]["id"]
        
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/payment-action",
            json={
                "telegram_user_id": ADMIN_USER_ID,
                "payment_id": payment_id,
                "action": "reject"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert data.get("new_status") == "rejected", f"Expected new_status=rejected, got {data.get('new_status')}"
        
        print(f"✅ Payment rejected: payment_id={payment_id}, new_status={data['new_status']}")
    
    def test_payment_action_invalid_action(self):
        """POST /api/miniapp/admin/payment-action with invalid action returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/payment-action",
            json={
                "telegram_user_id": ADMIN_USER_ID,
                "payment_id": "some-payment-id",
                "action": "invalid_action"
            }
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print(f"✅ Payment action correctly returns 400 for invalid action")
    
    def test_payment_action_returns_403_for_non_admin(self):
        """POST /api/miniapp/admin/payment-action returns 403 for non-admin"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/payment-action",
            json={
                "telegram_user_id": NON_ADMIN_USER_ID,
                "payment_id": "some-payment-id",
                "action": "approve"
            }
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✅ Payment action correctly returns 403 for non-admin")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
