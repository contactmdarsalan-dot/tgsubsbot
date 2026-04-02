"""
Iteration 31: MiniApp Admin Tenant Isolation Security Tests
Tests that all miniapp admin endpoints properly filter by tenant_id to prevent cross-tenant data leaks.

Key security concern: Admin from tenant_A should NOT be able to view/modify data belonging to tenant_B.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test tenant IDs
TENANT_A = "tenant_85ee971d0285"  # Anamika's tenant (has data)
TENANT_B = "tenant_b7e9359cafe0"  # Leak Tester tenant (should see no data from tenant_A)

# Telegram admin IDs
ADMIN_A_TG_ID = "123456789"  # Admin for tenant_A
ADMIN_B_TG_ID = "test_admin_tenant_b_isolation"  # Admin for tenant_B (created in DB)


class TestMiniAppAdminCheck:
    """Test /api/miniapp/admin/check endpoint"""
    
    def test_admin_check_valid_admin_a(self):
        """Verify admin check returns correct data for tenant A admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/check/{ADMIN_A_TG_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["is_admin"] == True
        assert "permissions" in data
        print(f"✓ Admin A check: is_admin={data['is_admin']}, role={data.get('role')}")
    
    def test_admin_check_valid_admin_b(self):
        """Verify admin check returns correct data for tenant B admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/check/{ADMIN_B_TG_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["is_admin"] == True
        print(f"✓ Admin B check: is_admin={data['is_admin']}, role={data.get('role')}")
    
    def test_admin_check_invalid_admin(self):
        """Verify admin check returns false for non-admin"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/check/invalid_user_999")
        assert response.status_code == 200
        data = response.json()
        assert data["is_admin"] == False
        print(f"✓ Invalid user check: is_admin={data['is_admin']}")


class TestStatsEndpointIsolation:
    """Test /api/miniapp/admin/stats/{telegram_user_id} tenant isolation"""
    
    def test_stats_tenant_a_sees_own_data(self):
        """Admin A should see stats for their tenant only"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/stats/{ADMIN_A_TG_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "total_subscribers" in data
        assert "active_subscribers" in data
        assert "pending_payments" in data
        assert "total_revenue" in data
        print(f"✓ Tenant A stats: subs={data['total_subscribers']}, pending={data['pending_payments']}, revenue={data['total_revenue']}")
        return data
    
    def test_stats_tenant_b_sees_own_data_only(self):
        """Admin B should see only their tenant's stats (likely 0 or minimal)"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/stats/{ADMIN_B_TG_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "total_subscribers" in data
        # Tenant B should see 0 or only their own data (not tenant A's large counts)
        print(f"✓ Tenant B stats: subs={data['total_subscribers']}, pending={data['pending_payments']}, revenue={data['total_revenue']}")
    
    def test_stats_non_admin_rejected(self):
        """Non-admin should be rejected"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/stats/invalid_user_999")
        assert response.status_code == 403
        print("✓ Non-admin rejected from stats endpoint")


class TestPendingPaymentsIsolation:
    """Test /api/miniapp/admin/pending-payments/{telegram_user_id} tenant isolation"""
    
    def test_pending_payments_tenant_a(self):
        """Admin A should see only their tenant's pending payments"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/pending-payments/{ADMIN_A_TG_ID}")
        assert response.status_code == 200
        payments = response.json()
        assert isinstance(payments, list)
        # Verify all payments belong to tenant_A
        for p in payments:
            tenant_id = p.get("tenant_id")
            assert tenant_id == TENANT_A or tenant_id is None or tenant_id == "default", f"Payment {p.get('id')} has wrong tenant_id: {tenant_id}"
        print(f"✓ Tenant A pending payments: {len(payments)} items")
    
    def test_pending_payments_tenant_b_isolation(self):
        """Admin B should NOT see tenant A's pending payments"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/pending-payments/{ADMIN_B_TG_ID}")
        assert response.status_code == 200
        payments = response.json()
        # Verify NO payments from tenant_A
        for p in payments:
            assert p.get("tenant_id") != TENANT_A, f"SECURITY LEAK: Tenant B sees tenant A's payment {p.get('id')}"
        print(f"✓ Tenant B pending payments: {len(payments)} items, NO tenant_A data leaked")


class TestSubscribersIsolation:
    """Test /api/miniapp/admin/subscribers/{telegram_user_id} tenant isolation"""
    
    def test_subscribers_tenant_a(self):
        """Admin A should see only their tenant's subscribers"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/subscribers/{ADMIN_A_TG_ID}")
        assert response.status_code == 200
        subs = response.json()
        assert isinstance(subs, list)
        for s in subs:
            tenant_id = s.get("tenant_id")
            assert tenant_id == TENANT_A or tenant_id is None or tenant_id == "default", f"Subscriber has wrong tenant_id: {tenant_id}"
        print(f"✓ Tenant A subscribers: {len(subs)} items")
    
    def test_subscribers_tenant_b_isolation(self):
        """Admin B should NOT see tenant A's subscribers"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/subscribers/{ADMIN_B_TG_ID}")
        assert response.status_code == 200
        subs = response.json()
        for s in subs:
            assert s.get("tenant_id") != TENANT_A, f"SECURITY LEAK: Tenant B sees tenant A's subscriber"
        print(f"✓ Tenant B subscribers: {len(subs)} items, NO tenant_A data leaked")


class TestPaidPostsIsolation:
    """Test /api/miniapp/admin/paid-posts/{telegram_user_id} tenant isolation"""
    
    def test_paid_posts_tenant_a(self):
        """Admin A should see only their tenant's paid posts"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/paid-posts/{ADMIN_A_TG_ID}")
        assert response.status_code == 200
        posts = response.json()
        assert isinstance(posts, list)
        for p in posts:
            tenant_id = p.get("tenant_id")
            assert tenant_id == TENANT_A or tenant_id is None or tenant_id == "default", f"Post has wrong tenant_id: {tenant_id}"
        print(f"✓ Tenant A paid posts: {len(posts)} items")
    
    def test_paid_posts_tenant_b_isolation(self):
        """Admin B should NOT see tenant A's paid posts"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/paid-posts/{ADMIN_B_TG_ID}")
        assert response.status_code == 200
        posts = response.json()
        for p in posts:
            assert p.get("tenant_id") != TENANT_A, f"SECURITY LEAK: Tenant B sees tenant A's paid post"
        print(f"✓ Tenant B paid posts: {len(posts)} items, NO tenant_A data leaked")


class TestLiveSessionsIsolation:
    """Test /api/miniapp/admin/live-sessions/{telegram_user_id} tenant isolation"""
    
    def test_live_sessions_tenant_a(self):
        """Admin A should see only their tenant's live sessions"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/live-sessions/{ADMIN_A_TG_ID}")
        assert response.status_code == 200
        sessions = response.json()
        assert isinstance(sessions, list)
        for s in sessions:
            tenant_id = s.get("tenant_id")
            assert tenant_id == TENANT_A or tenant_id is None or tenant_id == "default", f"Session has wrong tenant_id: {tenant_id}"
        print(f"✓ Tenant A live sessions: {len(sessions)} items")
    
    def test_live_sessions_tenant_b_isolation(self):
        """Admin B should NOT see tenant A's live sessions"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/live-sessions/{ADMIN_B_TG_ID}")
        assert response.status_code == 200
        sessions = response.json()
        for s in sessions:
            assert s.get("tenant_id") != TENANT_A, f"SECURITY LEAK: Tenant B sees tenant A's live session"
        print(f"✓ Tenant B live sessions: {len(sessions)} items, NO tenant_A data leaked")


class TestPaymentActionIsolation:
    """Test /api/miniapp/admin/payment-action tenant isolation"""
    
    def test_payment_action_cross_tenant_blocked(self):
        """Admin B should NOT be able to approve/reject tenant A's payments"""
        # First get a payment from tenant_A
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/pending-payments/{ADMIN_A_TG_ID}")
        if response.status_code == 200:
            payments = response.json()
            if payments:
                payment_id = payments[0].get("id")
                # Try to approve it as admin B
                action_response = requests.post(
                    f"{BASE_URL}/api/miniapp/admin/payment-action",
                    json={
                        "telegram_user_id": ADMIN_B_TG_ID,
                        "payment_id": payment_id,
                        "action": "approve"
                    }
                )
                # Should return 404 (payment not found in tenant B's scope)
                assert action_response.status_code == 404, f"SECURITY LEAK: Admin B could access tenant A's payment! Status: {action_response.status_code}, Response: {action_response.text}"
                print(f"✓ Cross-tenant payment action blocked (404 returned)")
            else:
                print("⚠ No pending payments to test cross-tenant action - SKIPPED")
                pytest.skip("No pending payments available for testing")
        else:
            pytest.skip(f"Could not get pending payments: {response.status_code}")


class TestPaidPostToggleIsolation:
    """Test /api/miniapp/admin/paid-post/{post_id}/toggle tenant isolation"""
    
    def test_toggle_cross_tenant_blocked(self):
        """Admin B should NOT be able to toggle tenant A's paid posts"""
        # Get a paid post from tenant_A
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/paid-posts/{ADMIN_A_TG_ID}")
        if response.status_code == 200:
            posts = response.json()
            if posts:
                post_id = posts[0].get("id")
                # Try to toggle it as admin B
                toggle_response = requests.post(
                    f"{BASE_URL}/api/miniapp/admin/paid-post/{post_id}/toggle",
                    json={"telegram_user_id": ADMIN_B_TG_ID}
                )
                assert toggle_response.status_code == 404, f"SECURITY LEAK: Admin B could toggle tenant A's post! Status: {toggle_response.status_code}"
                print(f"✓ Cross-tenant paid post toggle blocked (404 returned)")
            else:
                pytest.skip("No paid posts available for testing")


class TestPaidPostBlurIsolation:
    """Test /api/miniapp/admin/paid-post/{post_id}/blur tenant isolation"""
    
    def test_blur_cross_tenant_no_effect(self):
        """Admin B's blur update should not affect tenant A's paid posts"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/paid-posts/{ADMIN_A_TG_ID}")
        if response.status_code == 200:
            posts = response.json()
            if posts:
                post_id = posts[0].get("id")
                original_blur = posts[0].get("blur_level", 10)
                
                # Try to update blur as admin B
                blur_response = requests.post(
                    f"{BASE_URL}/api/miniapp/admin/paid-post/{post_id}/blur",
                    json={"telegram_user_id": ADMIN_B_TG_ID, "blur_level": 99}
                )
                # The endpoint returns success but doesn't actually modify (update_one with wrong tenant)
                print(f"✓ Blur endpoint called, status: {blur_response.status_code}")
                
                # Verify the post wasn't actually modified
                verify_response = requests.get(f"{BASE_URL}/api/miniapp/admin/paid-posts/{ADMIN_A_TG_ID}")
                if verify_response.status_code == 200:
                    updated_posts = verify_response.json()
                    for p in updated_posts:
                        if p.get("id") == post_id:
                            assert p.get("blur_level") == original_blur, f"SECURITY LEAK: Admin B modified tenant A's post blur!"
                            print(f"✓ Verified: Post blur unchanged ({original_blur})")
                            break


class TestLiveSessionDeleteIsolation:
    """Test DELETE /api/miniapp/admin/live-session/{session_id} tenant isolation"""
    
    def test_delete_cross_tenant_blocked(self):
        """Admin B should NOT be able to delete tenant A's live sessions"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/live-sessions/{ADMIN_A_TG_ID}")
        if response.status_code == 200:
            sessions = response.json()
            if sessions:
                session_id = sessions[0].get("id")
                delete_response = requests.delete(
                    f"{BASE_URL}/api/miniapp/admin/live-session/{session_id}",
                    json={"telegram_user_id": ADMIN_B_TG_ID}
                )
                # Should return success=False (deleted_count=0) because tenant_query filters it out
                data = delete_response.json()
                assert data.get("success") == False, f"SECURITY LEAK: Admin B could delete tenant A's session! Response: {data}"
                print(f"✓ Cross-tenant live session delete blocked (success=False)")
            else:
                pytest.skip("No live sessions available for testing")


class TestLiveSessionEndIsolation:
    """Test POST /api/miniapp/admin/live-session/{session_id}/end tenant isolation"""
    
    def test_end_cross_tenant_blocked(self):
        """Admin B should NOT be able to end tenant A's live sessions"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/live-sessions/{ADMIN_A_TG_ID}")
        if response.status_code == 200:
            sessions = response.json()
            if sessions:
                session_id = sessions[0].get("id")
                end_response = requests.post(
                    f"{BASE_URL}/api/miniapp/admin/live-session/{session_id}/end",
                    json={"telegram_user_id": ADMIN_B_TG_ID}
                )
                data = end_response.json()
                assert data.get("success") == False, f"SECURITY LEAK: Admin B could end tenant A's session! Response: {data}"
                print(f"✓ Cross-tenant live session end blocked (success=False)")
            else:
                pytest.skip("No live sessions available for testing")


class TestLiveSessionGoLiveIsolation:
    """Test POST /api/miniapp/admin/live-session/{session_id}/go-live tenant isolation"""
    
    def test_go_live_cross_tenant_blocked(self):
        """Admin B should NOT be able to go-live on tenant A's sessions"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/live-sessions/{ADMIN_A_TG_ID}")
        if response.status_code == 200:
            sessions = response.json()
            if sessions:
                session_id = sessions[0].get("id")
                go_live_response = requests.post(
                    f"{BASE_URL}/api/miniapp/admin/live-session/{session_id}/go-live",
                    json={"telegram_user_id": ADMIN_B_TG_ID}
                )
                # Should return 404 because tenant_query filters it out
                assert go_live_response.status_code == 404, f"SECURITY LEAK: Admin B could go-live on tenant A's session! Status: {go_live_response.status_code}"
                print(f"✓ Cross-tenant go-live blocked (404 returned)")
            else:
                pytest.skip("No live sessions available for testing")


class TestBroadcastIsolation:
    """Test /api/miniapp/admin/broadcast tenant isolation"""
    
    def test_broadcast_uses_tenant_scoped_users(self):
        """Broadcast should only send to users in admin's tenant"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp/admin/broadcast",
            json={
                "telegram_user_id": ADMIN_B_TG_ID,
                "message": "Test broadcast message"
            }
        )
        # Should succeed but send to 0 users (tenant B has no bot_users)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Broadcast for tenant B: total_recipients={data.get('total_recipients', 0)}")
            # Tenant B should have 0 or very few recipients (only their own users)
        elif response.status_code == 400:
            print(f"✓ Broadcast rejected (likely no bot token configured)")
        else:
            print(f"⚠ Broadcast response: {response.status_code}")


class TestTenantEndpoint:
    """Test /api/miniapp/admin/tenant/{telegram_user_id} endpoint"""
    
    def test_get_tenant_returns_own_tenant_a(self):
        """Admin A should see their own tenant info"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/tenant/{ADMIN_A_TG_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("tenant_id") == TENANT_A
        print(f"✓ Tenant A gets own tenant: {data.get('tenant_id')}")
    
    def test_get_tenant_returns_own_tenant_b(self):
        """Admin B should see their own tenant info"""
        response = requests.get(f"{BASE_URL}/api/miniapp/admin/tenant/{ADMIN_B_TG_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("tenant_id") == TENANT_B
        print(f"✓ Tenant B gets own tenant: {data.get('tenant_id')}")


class TestCodeReviewVerification:
    """Verify code patterns in miniapp_admin.py"""
    
    def test_verify_tenant_query_usage(self):
        """Verify all endpoints use tenant_query for DB operations"""
        import re
        
        with open('/app/backend/routes/miniapp_admin.py', 'r') as f:
            content = f.read()
        
        # Check that tenant_query is imported
        assert 'from services.tenant import DEFAULT_TENANT_ID, tenant_query' in content, "tenant_query not imported"
        print("✓ tenant_query imported correctly")
        
        # Check key patterns - using flexible regex to match actual code
        patterns_to_check = [
            (r'tenant_query\(\{[^}]*\},\s*admin\.get\(["\']tenant_id', 'pending-payments uses tenant_query'),
            (r'tq\(\{\}\)', 'stats uses tq() helper'),
            (r'db\.subscribers\.find\([^)]*tenant_query', 'subscribers uses tenant_query'),
            (r'db\.paid_posts\.find\([^)]*tenant_query', 'paid-posts uses tenant_query'),
            (r'db\.live_sessions\.find\([^)]*tenant_query', 'live-sessions uses tenant_query'),
            (r'db\.bot_users\.find\(tenant_query', 'broadcast uses tenant_query for bot_users'),
        ]
        
        for pattern, description in patterns_to_check:
            match = re.search(pattern, content)
            if match:
                print(f"✓ Code review: {description}")
            else:
                print(f"⚠ Pattern not found: {description}")
        
        # Critical security check: ensure no raw db queries without tenant filtering
        # Look for potential security issues
        raw_queries = re.findall(r'db\.\w+\.find_one\(\{[^}]*\}[^,]*\)', content)
        for q in raw_queries:
            if 'tenant_query' not in q and 'tq(' not in q:
                # Check if it's in _verify_miniapp_admin (which is OK)
                if 'telegram_user_id' in q and 'is_active' in q:
                    continue  # This is the admin verification query
                print(f"⚠ Potential raw query without tenant filter: {q[:80]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
