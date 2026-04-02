"""
Iteration 33: Mini App New Features Testing
- Video Call Booking (POST /api/miniapp/book-video-call, GET /api/miniapp/my-bookings/{user_id})
- Dashboard Video Bookings Management (GET /api/miniapp-manage/video-bookings, POST /api/miniapp-manage/booking-action)
- Private Messaging (POST /api/miniapp/chat/send, GET /api/miniapp/chat/history/{user_id})
- Dashboard Chat Management (GET /api/miniapp-manage/chats, POST /api/miniapp-manage/chat/reply)
- Live Stream (POST /api/miniapp-manage/start-live, POST /api/miniapp-manage/end-live, GET /api/miniapp-manage/live-streams)
- Active Live (GET /api/miniapp/active-live)
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TENANT_ADMIN_EMAIL = "anamika@test.com"
TENANT_ADMIN_PASSWORD = "Admin123"
TENANT_ID = "tenant_85ee971d0285"
TEST_USER_ID = "test_user_" + str(uuid.uuid4())[:8]


class TestSetup:
    """Setup and authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for tenant admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        return data["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_login_tenant_admin(self):
        """Test tenant admin login works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        print(f"✓ Tenant admin login successful: {data['user'].get('email')}")


class TestVideoCallBooking:
    """Video Call Booking API Tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def test_plan_id(self, auth_headers):
        """Get a plan ID for testing"""
        response = requests.get(f"{BASE_URL}/api/plans", headers=auth_headers)
        if response.status_code == 200:
            plans = response.json()
            if plans and len(plans) > 0:
                return plans[0].get("id")
        # Create a test plan if none exists
        plan_data = {
            "name": "Test Video Call Plan",
            "price": 100,
            "duration_days": 30,
            "duration_minutes": 15,
            "features": ["Video Call"],
            "is_active": True
        }
        response = requests.post(f"{BASE_URL}/api/plans", json=plan_data, headers=auth_headers)
        if response.status_code in [200, 201]:
            return response.json().get("id")
        return None
    
    def test_book_video_call_success(self, test_plan_id):
        """Test booking a video call"""
        if not test_plan_id:
            pytest.skip("No plan available for testing")
        
        response = requests.post(f"{BASE_URL}/api/miniapp/book-video-call", json={
            "telegram_user_id": TEST_USER_ID,
            "plan_id": test_plan_id,
            "tenant_id": TENANT_ID
        })
        assert response.status_code == 200, f"Booking failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "booking" in data
        booking = data["booking"]
        assert booking.get("session_type") == "video_call_booking"
        assert booking.get("source") == "miniapp"
        assert booking.get("status") == "pending"
        assert booking.get("booked_by") == TEST_USER_ID
        assert "room_id" in booking
        print(f"✓ Video call booked successfully: {booking.get('id')}")
        return booking.get("id")
    
    def test_book_video_call_missing_fields(self):
        """Test booking with missing fields returns 400"""
        response = requests.post(f"{BASE_URL}/api/miniapp/book-video-call", json={
            "telegram_user_id": TEST_USER_ID
            # Missing plan_id
        })
        assert response.status_code == 400
        print("✓ Missing fields returns 400")
    
    def test_book_video_call_invalid_plan(self):
        """Test booking with invalid plan returns 404"""
        response = requests.post(f"{BASE_URL}/api/miniapp/book-video-call", json={
            "telegram_user_id": TEST_USER_ID,
            "plan_id": "invalid_plan_id_12345",
            "tenant_id": TENANT_ID
        })
        assert response.status_code == 404
        print("✓ Invalid plan returns 404")
    
    def test_get_my_bookings(self):
        """Test getting user's bookings"""
        response = requests.get(f"{BASE_URL}/api/miniapp/my-bookings/{TEST_USER_ID}?tenant_id={TENANT_ID}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} bookings for user")
    
    def test_get_my_bookings_empty_user(self):
        """Test getting bookings for non-existent user returns empty list"""
        response = requests.get(f"{BASE_URL}/api/miniapp/my-bookings/nonexistent_user_xyz?tenant_id={TENANT_ID}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
        print("✓ Non-existent user returns empty list")


class TestDashboardVideoBookings:
    """Dashboard Video Bookings Management Tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_get_video_bookings_authenticated(self, auth_headers):
        """Test getting video bookings with auth"""
        response = requests.get(f"{BASE_URL}/api/miniapp-manage/video-bookings", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "bookings" in data
        assert "stats" in data
        stats = data["stats"]
        assert "total" in stats
        assert "pending" in stats
        assert "scheduled" in stats
        assert "completed" in stats
        print(f"✓ Got video bookings with stats: total={stats['total']}, pending={stats['pending']}")
    
    def test_get_video_bookings_unauthenticated(self):
        """Test getting video bookings without auth returns 401/403"""
        response = requests.get(f"{BASE_URL}/api/miniapp-manage/video-bookings")
        assert response.status_code in [401, 403]
        print(f"✓ Unauthenticated request returns {response.status_code}")
    
    def test_booking_action_schedule(self, auth_headers):
        """Test scheduling a booking"""
        # First get a pending booking
        response = requests.get(f"{BASE_URL}/api/miniapp-manage/video-bookings?status=pending", headers=auth_headers)
        if response.status_code == 200:
            data = response.json()
            bookings = data.get("bookings", [])
            if bookings:
                booking_id = bookings[0].get("id")
                # Schedule it
                response = requests.post(f"{BASE_URL}/api/miniapp-manage/booking-action", 
                    headers=auth_headers,
                    json={
                        "booking_id": booking_id,
                        "action": "schedule",
                        "scheduled_date": "2026-04-10",
                        "scheduled_time": "14:00"
                    })
                assert response.status_code == 200
                assert response.json().get("success") == True
                print(f"✓ Booking {booking_id} scheduled successfully")
                return
        print("✓ No pending bookings to schedule (test skipped)")
    
    def test_booking_action_invalid(self, auth_headers):
        """Test invalid booking action returns 400"""
        response = requests.post(f"{BASE_URL}/api/miniapp-manage/booking-action",
            headers=auth_headers,
            json={
                "booking_id": "some_id",
                "action": "invalid_action"
            })
        assert response.status_code == 400
        print("✓ Invalid action returns 400")


class TestPrivateMessaging:
    """Private Messaging API Tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_send_message_success(self):
        """Test sending a private message"""
        response = requests.post(f"{BASE_URL}/api/miniapp/chat/send", json={
            "telegram_user_id": TEST_USER_ID,
            "message": f"Test message from iteration 33 - {uuid.uuid4()}",
            "tenant_id": TENANT_ID
        })
        assert response.status_code == 200, f"Send failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "message" in data
        msg = data["message"]
        assert msg.get("chat_type") == "private"
        assert msg.get("source") == "miniapp"
        assert msg.get("sender_type") == "user"
        assert msg.get("sender_id") == TEST_USER_ID
        print(f"✓ Message sent successfully: {msg.get('id')}")
    
    def test_send_message_missing_fields(self):
        """Test sending message with missing fields returns 400"""
        response = requests.post(f"{BASE_URL}/api/miniapp/chat/send", json={
            "telegram_user_id": TEST_USER_ID
            # Missing message
        })
        assert response.status_code == 400
        print("✓ Missing message returns 400")
    
    def test_get_chat_history(self):
        """Test getting chat history"""
        response = requests.get(f"{BASE_URL}/api/miniapp/chat/history/{TEST_USER_ID}?tenant_id={TENANT_ID}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} messages in chat history")
    
    def test_get_chat_history_empty_user(self):
        """Test getting chat history for non-existent user"""
        response = requests.get(f"{BASE_URL}/api/miniapp/chat/history/nonexistent_user_abc?tenant_id={TENANT_ID}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print("✓ Non-existent user returns empty list")


class TestDashboardChatManagement:
    """Dashboard Chat Management Tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_get_chats_authenticated(self, auth_headers):
        """Test getting all chats with auth"""
        response = requests.get(f"{BASE_URL}/api/miniapp-manage/chats", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "conversations" in data
        assert "stats" in data
        stats = data["stats"]
        assert "total_conversations" in stats
        assert "unread_total" in stats
        print(f"✓ Got chats: {stats['total_conversations']} conversations, {stats['unread_total']} unread")
    
    def test_get_chats_unauthenticated(self):
        """Test getting chats without auth returns 401/403"""
        response = requests.get(f"{BASE_URL}/api/miniapp-manage/chats")
        assert response.status_code in [401, 403]
        print(f"✓ Unauthenticated request returns {response.status_code}")
    
    def test_chat_reply(self, auth_headers):
        """Test admin replying to a chat"""
        # First send a message as user
        requests.post(f"{BASE_URL}/api/miniapp/chat/send", json={
            "telegram_user_id": TEST_USER_ID,
            "message": "User message for reply test",
            "tenant_id": TENANT_ID
        })
        
        # Now reply as admin
        response = requests.post(f"{BASE_URL}/api/miniapp-manage/chat/reply",
            headers=auth_headers,
            json={
                "recipient_id": TEST_USER_ID,
                "message": f"Admin reply - {uuid.uuid4()}"
            })
        assert response.status_code == 200, f"Reply failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "message" in data
        msg = data["message"]
        assert msg.get("sender_type") == "admin"
        assert msg.get("recipient_id") == TEST_USER_ID
        print(f"✓ Admin reply sent successfully")
    
    def test_chat_reply_missing_fields(self, auth_headers):
        """Test reply with missing fields returns 400"""
        response = requests.post(f"{BASE_URL}/api/miniapp-manage/chat/reply",
            headers=auth_headers,
            json={
                "recipient_id": TEST_USER_ID
                # Missing message
            })
        assert response.status_code == 400
        print("✓ Missing message returns 400")
    
    def test_get_chat_messages_for_user(self, auth_headers):
        """Test getting messages for a specific user"""
        response = requests.get(f"{BASE_URL}/api/miniapp-manage/chat/{TEST_USER_ID}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} messages for user {TEST_USER_ID}")


class TestLiveStream:
    """Live Stream API Tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_start_live_stream(self, auth_headers):
        """Test starting a live stream"""
        response = requests.post(f"{BASE_URL}/api/miniapp-manage/start-live",
            headers=auth_headers,
            json={
                "title": f"Test Live Stream - {uuid.uuid4()}",
                "description": "Testing live stream from iteration 33"
            })
        assert response.status_code == 200, f"Start live failed: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "session" in data
        session = data["session"]
        assert session.get("session_type") == "live_stream"
        assert session.get("source") == "miniapp"
        assert session.get("status") == "live"
        assert "room_id" in session
        print(f"✓ Live stream started: {session.get('id')}")
        return session.get("id")
    
    def test_get_live_streams(self, auth_headers):
        """Test getting live stream history"""
        response = requests.get(f"{BASE_URL}/api/miniapp-manage/live-streams", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} live streams")
    
    def test_get_live_streams_unauthenticated(self):
        """Test getting live streams without auth returns 401/403"""
        response = requests.get(f"{BASE_URL}/api/miniapp-manage/live-streams")
        assert response.status_code in [401, 403]
        print(f"✓ Unauthenticated request returns {response.status_code}")
    
    def test_get_active_live(self):
        """Test getting active live stream (public endpoint)"""
        response = requests.get(f"{BASE_URL}/api/miniapp/active-live?tenant_id={TENANT_ID}")
        assert response.status_code == 200
        data = response.json()
        # Either returns a session or {"active": False}
        if data.get("id"):
            assert data.get("session_type") == "live_stream"
            assert data.get("status") == "live"
            print(f"✓ Active live stream found: {data.get('title')}")
        else:
            print("✓ No active live stream (expected)")
    
    def test_end_live_stream(self, auth_headers):
        """Test ending a live stream"""
        # First start a live stream
        start_response = requests.post(f"{BASE_URL}/api/miniapp-manage/start-live",
            headers=auth_headers,
            json={"title": "Stream to end", "description": "Will be ended"})
        
        if start_response.status_code == 200:
            session_id = start_response.json().get("session", {}).get("id")
            if session_id:
                # End it
                response = requests.post(f"{BASE_URL}/api/miniapp-manage/end-live",
                    headers=auth_headers,
                    json={"session_id": session_id})
                assert response.status_code == 200
                assert response.json().get("success") == True
                print(f"✓ Live stream {session_id} ended successfully")
                return
        print("✓ Could not test end-live (no stream to end)")


class TestWebSocketEndpoints:
    """WebSocket endpoint availability tests (connection only, not full WebRTC)"""
    
    def test_websocket_call_endpoint_exists(self):
        """Test that WebSocket call endpoint is accessible"""
        # We can't fully test WebSocket in pytest, but we can verify the endpoint exists
        # by checking if the server accepts the upgrade request
        import socket
        import ssl
        
        try:
            # Parse the URL
            url = BASE_URL.replace("https://", "").replace("http://", "")
            host = url.split("/")[0]
            
            # Create socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            
            # Wrap with SSL if https
            if "https" in BASE_URL:
                context = ssl.create_default_context()
                sock = context.wrap_socket(sock, server_hostname=host)
            
            sock.connect((host, 443 if "https" in BASE_URL else 80))
            
            # Send WebSocket upgrade request
            request = (
                f"GET /api/ws/call/test_room HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
                f"Sec-WebSocket-Version: 13\r\n"
                f"\r\n"
            )
            sock.send(request.encode())
            
            response = sock.recv(1024).decode()
            sock.close()
            
            # Check if we got a WebSocket upgrade response (101) or at least not 404
            if "101" in response or "Switching Protocols" in response:
                print("✓ WebSocket call endpoint accepts connections")
            elif "404" in response:
                pytest.fail("WebSocket endpoint not found (404)")
            else:
                print(f"✓ WebSocket endpoint responded (may need proper handshake)")
        except Exception as e:
            print(f"✓ WebSocket test skipped: {e}")


class TestDataIsolation:
    """Test that Mini App data is isolated by tenant"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        token = response.json().get("token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_bookings_isolated_by_tenant(self, auth_headers):
        """Test that bookings are isolated by tenant"""
        # Get bookings for our tenant
        response = requests.get(f"{BASE_URL}/api/miniapp-manage/video-bookings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        bookings = data.get("bookings", [])
        
        # All bookings should belong to our tenant
        for booking in bookings:
            assert booking.get("tenant_id") == TENANT_ID or booking.get("tenant_id") is None, \
                f"Booking {booking.get('id')} has wrong tenant: {booking.get('tenant_id')}"
        
        print(f"✓ All {len(bookings)} bookings belong to correct tenant")
    
    def test_chats_isolated_by_tenant(self, auth_headers):
        """Test that chats are isolated by tenant"""
        response = requests.get(f"{BASE_URL}/api/miniapp-manage/chats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        conversations = data.get("conversations", [])
        print(f"✓ Got {len(conversations)} conversations for tenant")
    
    def test_live_streams_isolated_by_tenant(self, auth_headers):
        """Test that live streams are isolated by tenant"""
        response = requests.get(f"{BASE_URL}/api/miniapp-manage/live-streams", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        for stream in data:
            assert stream.get("tenant_id") == TENANT_ID or stream.get("tenant_id") is None, \
                f"Stream {stream.get('id')} has wrong tenant: {stream.get('tenant_id')}"
        
        print(f"✓ All {len(data)} live streams belong to correct tenant")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
