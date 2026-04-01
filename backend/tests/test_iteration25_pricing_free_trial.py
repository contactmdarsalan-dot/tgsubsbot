"""
Iteration 25: Dynamic Pricing Page & Free Trial Activation Tests
Tests:
1. GET /api/public/subscription-plans - Public endpoint returns active plans (no auth)
2. POST /api/dashboard-subscription/activate-free - Activates free trial for logged-in user
3. Duplicate prevention - Second call returns 400
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"
SUPER_ADMIN_PASSWORD = "Sumit@8958"


class TestPublicSubscriptionPlans:
    """Test GET /api/public/subscription-plans - Public endpoint (no auth required)"""
    
    def test_public_plans_returns_200(self):
        """Public plans endpoint should return 200 without auth"""
        response = requests.get(f"{BASE_URL}/api/public/subscription-plans")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: Public plans endpoint returns 200")
    
    def test_public_plans_returns_list(self):
        """Public plans should return a list of plans"""
        response = requests.get(f"{BASE_URL}/api/public/subscription-plans")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"PASS: Public plans returns list with {len(data)} plans")
    
    def test_public_plans_contains_free_plan(self):
        """Public plans should contain a Free plan with price 0"""
        response = requests.get(f"{BASE_URL}/api/public/subscription-plans")
        assert response.status_code == 200
        plans = response.json()
        
        free_plans = [p for p in plans if p.get("price", -1) == 0]
        assert len(free_plans) > 0, "No free plan found in public plans"
        
        free_plan = free_plans[0]
        assert "name" in free_plan, "Free plan missing 'name' field"
        assert "duration_days" in free_plan, "Free plan missing 'duration_days' field"
        assert "features" in free_plan, "Free plan missing 'features' field"
        print(f"PASS: Free plan found: {free_plan.get('name')} with {free_plan.get('duration_days')} days")
    
    def test_public_plans_contains_paid_plan(self):
        """Public plans should contain at least one paid plan"""
        response = requests.get(f"{BASE_URL}/api/public/subscription-plans")
        assert response.status_code == 200
        plans = response.json()
        
        paid_plans = [p for p in plans if p.get("price", 0) > 0]
        assert len(paid_plans) > 0, "No paid plan found in public plans"
        
        paid_plan = paid_plans[0]
        assert paid_plan.get("price") > 0, "Paid plan should have price > 0"
        print(f"PASS: Paid plan found: {paid_plan.get('name')} at Rs.{paid_plan.get('price')}")
    
    def test_public_plans_has_popular_flag(self):
        """At least one plan should have is_popular=True"""
        response = requests.get(f"{BASE_URL}/api/public/subscription-plans")
        assert response.status_code == 200
        plans = response.json()
        
        popular_plans = [p for p in plans if p.get("is_popular")]
        assert len(popular_plans) > 0, "No popular plan found"
        print(f"PASS: Popular plan found: {popular_plans[0].get('name')}")
    
    def test_public_plans_structure(self):
        """Each plan should have required fields"""
        response = requests.get(f"{BASE_URL}/api/public/subscription-plans")
        assert response.status_code == 200
        plans = response.json()
        
        required_fields = ["id", "name", "price", "duration_days", "is_active"]
        for plan in plans:
            for field in required_fields:
                assert field in plan, f"Plan missing required field: {field}"
            assert plan.get("is_active") == True, "Public plans should only return active plans"
        print(f"PASS: All {len(plans)} plans have required structure")


class TestFreeTrialActivation:
    """Test POST /api/dashboard-subscription/activate-free"""
    
    @pytest.fixture
    def new_user_token(self):
        """Register a new user and return their token"""
        unique_email = f"test_free_trial_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"name": "Free Trial Test", "email": unique_email, "password": "Test123!"}
        )
        assert response.status_code == 200, f"Registration failed: {response.text}"
        data = response.json()
        return data.get("token"), data.get("user", {})
    
    def test_activate_free_requires_auth(self):
        """Activate free endpoint should require authentication"""
        response = requests.post(f"{BASE_URL}/api/dashboard-subscription/activate-free")
        assert response.status_code in [401, 403, 422], f"Expected auth error, got {response.status_code}"
        print("PASS: Activate free requires authentication")
    
    def test_activate_free_success(self, new_user_token):
        """New user can activate free trial"""
        token, user = new_user_token
        
        # Check if user already has trial from registration
        initial_status = user.get("dashboard_subscription_status", "")
        
        # If user already has trial status, the endpoint should still work
        # (it only blocks "active" status)
        response = requests.post(
            f"{BASE_URL}/api/dashboard-subscription/activate-free",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if initial_status == "active":
            assert response.status_code == 400, "Should fail for already active user"
            print("PASS: User already had active status, correctly rejected")
        else:
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            data = response.json()
            assert "message" in data, "Response missing 'message'"
            assert "plan_name" in data, "Response missing 'plan_name'"
            assert "trial_end" in data, "Response missing 'trial_end'"
            assert "duration_days" in data, "Response missing 'duration_days'"
            print(f"PASS: Free trial activated - {data.get('plan_name')} for {data.get('duration_days')} days")
    
    def test_activate_free_sets_correct_fields(self, new_user_token):
        """After activation, user should have correct subscription fields"""
        token, user = new_user_token
        
        # Activate free trial
        requests.post(
            f"{BASE_URL}/api/dashboard-subscription/activate-free",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Login again to get updated user data
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": user.get("email"), "password": "Test123!"}
        )
        assert response.status_code == 200
        updated_user = response.json().get("user", {})
        
        assert updated_user.get("dashboard_subscription_status") == "active", \
            f"Expected 'active' status, got {updated_user.get('dashboard_subscription_status')}"
        assert updated_user.get("dashboard_plan") is not None, "dashboard_plan should be set"
        assert updated_user.get("dashboard_subscription_end") is not None, "dashboard_subscription_end should be set"
        print(f"PASS: User fields updated - status={updated_user.get('dashboard_subscription_status')}, plan={updated_user.get('dashboard_plan')}")
    
    def test_activate_free_duplicate_prevention(self, new_user_token):
        """Second activation attempt should fail with 400"""
        token, user = new_user_token
        
        # First activation
        response1 = requests.post(
            f"{BASE_URL}/api/dashboard-subscription/activate-free",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Second activation should fail
        response2 = requests.post(
            f"{BASE_URL}/api/dashboard-subscription/activate-free",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response2.status_code == 400, f"Expected 400, got {response2.status_code}"
        data = response2.json()
        assert "already have an active subscription" in data.get("detail", "").lower(), \
            f"Expected 'already have an active subscription' message, got: {data}"
        print("PASS: Duplicate activation correctly rejected with 400")


class TestExistingUserWithActiveSubscription:
    """Test that users with existing active subscription cannot activate free trial"""
    
    def test_active_user_cannot_activate_free(self):
        """User with active subscription should get 400"""
        # Login as existing user with active subscription
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "anamika@test.com", "password": "Admin123"}
        )
        
        if response.status_code != 200:
            pytest.skip("Test user anamika@test.com not available")
        
        token = response.json().get("token")
        user = response.json().get("user", {})
        
        # Try to activate free trial
        response = requests.post(
            f"{BASE_URL}/api/dashboard-subscription/activate-free",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Should fail if user already has active subscription
        if user.get("dashboard_subscription_status") == "active":
            assert response.status_code == 400, f"Expected 400, got {response.status_code}"
            print("PASS: Active user correctly rejected from free trial activation")
        else:
            print(f"INFO: User status is {user.get('dashboard_subscription_status')}, not 'active'")


class TestPlanDataIntegrity:
    """Test that plan data is consistent and valid"""
    
    def test_plans_sorted_by_price(self):
        """Plans should be sorted by price ascending"""
        response = requests.get(f"{BASE_URL}/api/public/subscription-plans")
        assert response.status_code == 200
        plans = response.json()
        
        prices = [p.get("price", 0) for p in plans]
        assert prices == sorted(prices), f"Plans not sorted by price: {prices}"
        print(f"PASS: Plans sorted by price: {prices}")
    
    def test_free_plan_has_17_days(self):
        """Free plan should have 17 days duration as per requirements"""
        response = requests.get(f"{BASE_URL}/api/public/subscription-plans")
        assert response.status_code == 200
        plans = response.json()
        
        free_plans = [p for p in plans if p.get("price", -1) == 0]
        if free_plans:
            free_plan = free_plans[0]
            assert free_plan.get("duration_days") == 17, \
                f"Free plan should have 17 days, got {free_plan.get('duration_days')}"
            print(f"PASS: Free plan has {free_plan.get('duration_days')} days")
    
    def test_lifetime_plan_has_75000_price(self):
        """Lifetime plan should have Rs.75,000 price as per requirements"""
        response = requests.get(f"{BASE_URL}/api/public/subscription-plans")
        assert response.status_code == 200
        plans = response.json()
        
        lifetime_plans = [p for p in plans if "lifetime" in p.get("name", "").lower()]
        if lifetime_plans:
            lifetime_plan = lifetime_plans[0]
            assert lifetime_plan.get("price") == 75000, \
                f"Lifetime plan should cost 75000, got {lifetime_plan.get('price')}"
            assert lifetime_plan.get("is_popular") == True, \
                "Lifetime plan should be marked as popular"
            print(f"PASS: Lifetime plan has Rs.{lifetime_plan.get('price')} and is_popular={lifetime_plan.get('is_popular')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
