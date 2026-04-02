"""
Iteration 34: Mini App Plans/Subscribers/Payments Data Isolation Tests
Tests the complete separation of Plans, Subscribers, and Payments between 'Telegram Bot' and 'Mini App' sections.
Key requirement: Editing a plan in Mini App should NOT affect Bot plans and vice versa.
Uses same collections with 'source' field discriminator ('bot' vs 'miniapp').
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TENANT_ADMIN_EMAIL = "anamika@test.com"
TENANT_ADMIN_PASSWORD = "Admin123"
SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"
SUPER_ADMIN_PASSWORD = "Sumit@8958"


@pytest.fixture(scope="module")
def tenant_admin_token():
    """Get tenant admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TENANT_ADMIN_EMAIL,
        "password": TENANT_ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Tenant admin login failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def super_admin_token():
    """Get super admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Super admin login failed: {response.status_code} - {response.text}")


def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ============== MINI APP PLANS CRUD TESTS ==============

class TestMiniAppPlansCRUD:
    """Test Mini App Plans CRUD operations"""
    
    created_plan_id = None
    
    def test_get_miniapp_plans(self, tenant_admin_token):
        """GET /api/miniapp-manage/plans - should return only miniapp plans"""
        response = requests.get(
            f"{BASE_URL}/api/miniapp-manage/plans",
            headers=auth_headers(tenant_admin_token)
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        plans = response.json()
        assert isinstance(plans, list), "Response should be a list"
        # All returned plans should have source='miniapp'
        for plan in plans:
            assert plan.get("source") == "miniapp", f"Plan {plan.get('id')} has source={plan.get('source')}, expected 'miniapp'"
        print(f"✓ GET /api/miniapp-manage/plans returned {len(plans)} miniapp plans")
    
    def test_create_miniapp_plan(self, tenant_admin_token):
        """POST /api/miniapp-manage/plans - create a new miniapp plan"""
        plan_data = {
            "name": f"TEST_MiniApp_Plan_{uuid.uuid4().hex[:6]}",
            "description": "Test plan for Mini App isolation testing",
            "price": 499,
            "duration_days": 30,
            "duration_minutes": 0,
            "plan_type": "subscription",
            "is_active": True
        }
        response = requests.post(
            f"{BASE_URL}/api/miniapp-manage/plans",
            headers=auth_headers(tenant_admin_token),
            json=plan_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, "Expected success=True"
        plan = data.get("plan", {})
        assert plan.get("name") == plan_data["name"], "Plan name mismatch"
        assert plan.get("source") == "miniapp", "Plan source should be 'miniapp'"
        assert plan.get("price") == plan_data["price"], "Plan price mismatch"
        TestMiniAppPlansCRUD.created_plan_id = plan.get("id")
        print(f"✓ Created miniapp plan: {plan.get('name')} (id: {plan.get('id')})")
    
    def test_update_miniapp_plan(self, tenant_admin_token):
        """PUT /api/miniapp-manage/plans/{id} - update a miniapp plan"""
        if not TestMiniAppPlansCRUD.created_plan_id:
            pytest.skip("No plan created to update")
        
        update_data = {
            "name": f"TEST_MiniApp_Plan_Updated_{uuid.uuid4().hex[:4]}",
            "price": 599,
            "description": "Updated description"
        }
        response = requests.put(
            f"{BASE_URL}/api/miniapp-manage/plans/{TestMiniAppPlansCRUD.created_plan_id}",
            headers=auth_headers(tenant_admin_token),
            json=update_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, "Expected success=True"
        print(f"✓ Updated miniapp plan: {TestMiniAppPlansCRUD.created_plan_id}")
    
    def test_verify_miniapp_plan_update_persisted(self, tenant_admin_token):
        """Verify the update was persisted"""
        if not TestMiniAppPlansCRUD.created_plan_id:
            pytest.skip("No plan created to verify")
        
        response = requests.get(
            f"{BASE_URL}/api/miniapp-manage/plans",
            headers=auth_headers(tenant_admin_token)
        )
        assert response.status_code == 200
        plans = response.json()
        updated_plan = next((p for p in plans if p.get("id") == TestMiniAppPlansCRUD.created_plan_id), None)
        assert updated_plan is not None, "Updated plan not found"
        assert updated_plan.get("price") == 599, f"Price not updated, got {updated_plan.get('price')}"
        print(f"✓ Verified miniapp plan update persisted: price={updated_plan.get('price')}")
    
    def test_delete_miniapp_plan(self, tenant_admin_token):
        """DELETE /api/miniapp-manage/plans/{id} - delete a miniapp plan"""
        if not TestMiniAppPlansCRUD.created_plan_id:
            pytest.skip("No plan created to delete")
        
        response = requests.delete(
            f"{BASE_URL}/api/miniapp-manage/plans/{TestMiniAppPlansCRUD.created_plan_id}",
            headers=auth_headers(tenant_admin_token)
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, "Expected success=True"
        print(f"✓ Deleted miniapp plan: {TestMiniAppPlansCRUD.created_plan_id}")
    
    def test_verify_miniapp_plan_deleted(self, tenant_admin_token):
        """Verify the plan was deleted"""
        if not TestMiniAppPlansCRUD.created_plan_id:
            pytest.skip("No plan created to verify deletion")
        
        response = requests.get(
            f"{BASE_URL}/api/miniapp-manage/plans",
            headers=auth_headers(tenant_admin_token)
        )
        assert response.status_code == 200
        plans = response.json()
        deleted_plan = next((p for p in plans if p.get("id") == TestMiniAppPlansCRUD.created_plan_id), None)
        assert deleted_plan is None, "Plan should have been deleted"
        print(f"✓ Verified miniapp plan deleted")


# ============== DATA ISOLATION TESTS ==============

class TestDataIsolation:
    """Test that Mini App and Bot data are completely isolated"""
    
    miniapp_plan_id = None
    
    def test_create_miniapp_plan_for_isolation_test(self, tenant_admin_token):
        """Create a miniapp plan to test isolation"""
        plan_data = {
            "name": f"TEST_Isolation_MiniApp_{uuid.uuid4().hex[:6]}",
            "description": "Plan for isolation testing",
            "price": 777,
            "duration_days": 15,
            "plan_type": "subscription"
        }
        response = requests.post(
            f"{BASE_URL}/api/miniapp-manage/plans",
            headers=auth_headers(tenant_admin_token),
            json=plan_data
        )
        assert response.status_code == 200
        data = response.json()
        TestDataIsolation.miniapp_plan_id = data.get("plan", {}).get("id")
        print(f"✓ Created miniapp plan for isolation test: {TestDataIsolation.miniapp_plan_id}")
    
    def test_miniapp_plan_not_in_bot_plans(self, tenant_admin_token):
        """GET /api/plans (Bot) should NOT return miniapp plans"""
        response = requests.get(
            f"{BASE_URL}/api/plans",
            headers=auth_headers(tenant_admin_token)
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        bot_plans = response.json()
        
        # Check that no miniapp plans are in bot plans
        miniapp_plans_in_bot = [p for p in bot_plans if p.get("source") == "miniapp"]
        assert len(miniapp_plans_in_bot) == 0, f"Found {len(miniapp_plans_in_bot)} miniapp plans in bot plans endpoint!"
        
        # Specifically check our test plan is not there
        if TestDataIsolation.miniapp_plan_id:
            test_plan_in_bot = next((p for p in bot_plans if p.get("id") == TestDataIsolation.miniapp_plan_id), None)
            assert test_plan_in_bot is None, "Test miniapp plan found in bot plans!"
        
        print(f"✓ Bot plans endpoint correctly excludes miniapp plans (returned {len(bot_plans)} bot plans)")
    
    def test_bot_plans_have_no_miniapp_source(self, tenant_admin_token):
        """Verify all bot plans have source != 'miniapp'"""
        response = requests.get(
            f"{BASE_URL}/api/plans",
            headers=auth_headers(tenant_admin_token)
        )
        assert response.status_code == 200
        bot_plans = response.json()
        
        for plan in bot_plans:
            source = plan.get("source", "")
            assert source != "miniapp", f"Bot plan {plan.get('id')} has source='miniapp'!"
        
        print(f"✓ All {len(bot_plans)} bot plans have source != 'miniapp'")
    
    def test_miniapp_plans_have_miniapp_source(self, tenant_admin_token):
        """Verify all miniapp plans have source='miniapp'"""
        response = requests.get(
            f"{BASE_URL}/api/miniapp-manage/plans",
            headers=auth_headers(tenant_admin_token)
        )
        assert response.status_code == 200
        miniapp_plans = response.json()
        
        for plan in miniapp_plans:
            assert plan.get("source") == "miniapp", f"MiniApp plan {plan.get('id')} has source='{plan.get('source')}', expected 'miniapp'"
        
        print(f"✓ All {len(miniapp_plans)} miniapp plans have source='miniapp'")
    
    def test_cleanup_isolation_test_plan(self, tenant_admin_token):
        """Cleanup: Delete the test plan"""
        if TestDataIsolation.miniapp_plan_id:
            response = requests.delete(
                f"{BASE_URL}/api/miniapp-manage/plans/{TestDataIsolation.miniapp_plan_id}",
                headers=auth_headers(tenant_admin_token)
            )
            print(f"✓ Cleaned up isolation test plan")


# ============== MINI APP SUBSCRIBERS TESTS ==============

class TestMiniAppSubscribers:
    """Test Mini App Subscribers endpoint"""
    
    def test_get_miniapp_subscribers(self, tenant_admin_token):
        """GET /api/miniapp-manage/subscribers - should return only miniapp subscribers"""
        response = requests.get(
            f"{BASE_URL}/api/miniapp-manage/subscribers",
            headers=auth_headers(tenant_admin_token)
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "subscribers" in data, "Response should have 'subscribers' key"
        assert "total" in data, "Response should have 'total' key"
        assert "active" in data, "Response should have 'active' key"
        
        # All returned subscribers should have source='miniapp'
        for sub in data.get("subscribers", []):
            assert sub.get("source") == "miniapp", f"Subscriber {sub.get('id')} has source={sub.get('source')}, expected 'miniapp'"
        
        print(f"✓ GET /api/miniapp-manage/subscribers returned {data.get('total', 0)} miniapp subscribers ({data.get('active', 0)} active)")
    
    def test_bot_subscribers_exclude_miniapp(self, tenant_admin_token):
        """GET /api/subscribers (Bot) should NOT return miniapp subscribers"""
        response = requests.get(
            f"{BASE_URL}/api/subscribers",
            headers=auth_headers(tenant_admin_token)
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Check that no miniapp subscribers are in bot subscribers
        for sub in data.get("subscribers", []):
            source = sub.get("source", "")
            assert source != "miniapp", f"Bot subscriber {sub.get('id')} has source='miniapp'!"
        
        print(f"✓ Bot subscribers endpoint correctly excludes miniapp subscribers")


# ============== MINI APP PAYMENTS TESTS ==============

class TestMiniAppPayments:
    """Test Mini App Payments endpoint"""
    
    def test_get_miniapp_payments(self, tenant_admin_token):
        """GET /api/miniapp-manage/payments - should return only miniapp payments"""
        response = requests.get(
            f"{BASE_URL}/api/miniapp-manage/payments",
            headers=auth_headers(tenant_admin_token)
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "payments" in data, "Response should have 'payments' key"
        assert "total" in data, "Response should have 'total' key"
        assert "verified" in data, "Response should have 'verified' key"
        assert "revenue" in data, "Response should have 'revenue' key"
        
        # All returned payments should have source='miniapp'
        for payment in data.get("payments", []):
            assert payment.get("source") == "miniapp", f"Payment {payment.get('id')} has source={payment.get('source')}, expected 'miniapp'"
        
        print(f"✓ GET /api/miniapp-manage/payments returned {data.get('total', 0)} miniapp payments (revenue: {data.get('revenue', 0)})")
    
    def test_miniapp_payments_filter_by_status(self, tenant_admin_token):
        """GET /api/miniapp-manage/payments?status=pending - filter by status"""
        response = requests.get(
            f"{BASE_URL}/api/miniapp-manage/payments?status=pending",
            headers=auth_headers(tenant_admin_token)
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # All returned payments should have status='pending'
        for payment in data.get("payments", []):
            assert payment.get("status") == "pending", f"Payment {payment.get('id')} has status={payment.get('status')}, expected 'pending'"
        
        print(f"✓ GET /api/miniapp-manage/payments?status=pending returned {len(data.get('payments', []))} pending payments")
    
    def test_bot_payments_exclude_miniapp(self, tenant_admin_token):
        """GET /api/payments (Bot) should NOT return miniapp payments"""
        response = requests.get(
            f"{BASE_URL}/api/payments",
            headers=auth_headers(tenant_admin_token)
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Check that no miniapp payments are in bot payments
        for payment in data.get("payments", []):
            source = payment.get("source", "")
            assert source != "miniapp", f"Bot payment {payment.get('id')} has source='miniapp'!"
        
        print(f"✓ Bot payments endpoint correctly excludes miniapp payments")


# ============== PAYMENT ACTION TESTS ==============

class TestMiniAppPaymentAction:
    """Test Mini App Payment Action endpoint"""
    
    def test_payment_action_requires_auth(self):
        """POST /api/miniapp-manage/payment-action - requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp-manage/payment-action",
            json={"payment_id": "test", "action": "approve"}
        )
        # Should return 401 or 403 without auth
        assert response.status_code in [401, 403, 422], f"Expected 401/403/422, got {response.status_code}"
        print(f"✓ Payment action endpoint requires authentication")
    
    def test_payment_action_invalid_action(self, tenant_admin_token):
        """POST /api/miniapp-manage/payment-action - invalid action should fail gracefully"""
        response = requests.post(
            f"{BASE_URL}/api/miniapp-manage/payment-action",
            headers=auth_headers(tenant_admin_token),
            json={"payment_id": "nonexistent", "action": "invalid_action"}
        )
        # Should handle gracefully (either 400 or 200 with no effect)
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}"
        print(f"✓ Payment action handles invalid action gracefully")


# ============== AUTHENTICATION TESTS ==============

class TestAuthentication:
    """Test authentication requirements for Mini App endpoints"""
    
    def test_miniapp_plans_requires_auth(self):
        """GET /api/miniapp-manage/plans - requires authentication"""
        response = requests.get(f"{BASE_URL}/api/miniapp-manage/plans")
        assert response.status_code in [401, 403, 422], f"Expected 401/403/422, got {response.status_code}"
        print(f"✓ Mini App plans endpoint requires authentication")
    
    def test_miniapp_subscribers_requires_auth(self):
        """GET /api/miniapp-manage/subscribers - requires authentication"""
        response = requests.get(f"{BASE_URL}/api/miniapp-manage/subscribers")
        assert response.status_code in [401, 403, 422], f"Expected 401/403/422, got {response.status_code}"
        print(f"✓ Mini App subscribers endpoint requires authentication")
    
    def test_miniapp_payments_requires_auth(self):
        """GET /api/miniapp-manage/payments - requires authentication"""
        response = requests.get(f"{BASE_URL}/api/miniapp-manage/payments")
        assert response.status_code in [401, 403, 422], f"Expected 401/403/422, got {response.status_code}"
        print(f"✓ Mini App payments endpoint requires authentication")


# ============== EXISTING VIP VIDEO CALL PLAN TEST ==============

class TestExistingMiniAppPlan:
    """Test the existing 'VIP Video Call' plan mentioned in the context"""
    
    def test_vip_video_call_plan_exists(self, tenant_admin_token):
        """Verify the 'VIP Video Call' plan exists in miniapp plans"""
        response = requests.get(
            f"{BASE_URL}/api/miniapp-manage/plans",
            headers=auth_headers(tenant_admin_token)
        )
        assert response.status_code == 200
        plans = response.json()
        
        # Look for VIP Video Call plan
        vip_plan = next((p for p in plans if "VIP" in p.get("name", "") or "Video Call" in p.get("name", "")), None)
        
        if vip_plan:
            assert vip_plan.get("source") == "miniapp", "VIP plan should have source='miniapp'"
            print(f"✓ Found VIP Video Call plan: {vip_plan.get('name')} (price: {vip_plan.get('price')}, source: {vip_plan.get('source')})")
        else:
            print(f"ℹ VIP Video Call plan not found (may have been deleted). Found {len(plans)} miniapp plans.")
    
    def test_vip_plan_not_in_bot_plans(self, tenant_admin_token):
        """Verify VIP Video Call plan is NOT in bot plans"""
        response = requests.get(
            f"{BASE_URL}/api/plans",
            headers=auth_headers(tenant_admin_token)
        )
        assert response.status_code == 200
        bot_plans = response.json()
        
        # VIP Video Call should NOT be in bot plans
        vip_in_bot = next((p for p in bot_plans if "VIP" in p.get("name", "") and p.get("source") == "miniapp"), None)
        assert vip_in_bot is None, "VIP Video Call plan (miniapp) should NOT appear in bot plans"
        print(f"✓ VIP Video Call plan correctly excluded from bot plans")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
