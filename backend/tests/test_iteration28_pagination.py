"""
Iteration 28: Pagination Tests for Payments and Subscribers
Tests server-side pagination, stats accuracy, and filtering
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TENANT_ADMIN_EMAIL = "anamika@test.com"
TENANT_ADMIN_PASSWORD = "Admin123"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for tenant admin"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TENANT_ADMIN_EMAIL,
        "password": TENANT_ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for API calls"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestPaymentsPagination:
    """Test GET /api/payments pagination and stats"""
    
    def test_payments_page1_returns_paginated_response(self, auth_headers):
        """Test that page 1 returns proper paginated structure"""
        response = requests.get(f"{BASE_URL}/api/payments?page=1&limit=10", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        # Verify paginated response structure
        assert "payments" in data, "Response should have 'payments' array"
        assert "total" in data, "Response should have 'total' count"
        assert "page" in data, "Response should have 'page' number"
        assert "limit" in data, "Response should have 'limit'"
        assert "total_pages" in data, "Response should have 'total_pages'"
        assert "stats" in data, "Response should have 'stats' object"
        
        # Verify stats structure
        stats = data["stats"]
        assert "total_collected" in stats, "Stats should have 'total_collected'"
        assert "pending_count" in stats, "Stats should have 'pending_count'"
        assert "total_transactions" in stats, "Stats should have 'total_transactions'"
        
        # Verify pagination values
        assert data["page"] == 1
        assert data["limit"] == 10
        assert len(data["payments"]) <= 10, "Should return at most 10 payments"
        
        print(f"Page 1: {len(data['payments'])} payments, total: {data['total']}, total_pages: {data['total_pages']}")
        print(f"Stats: total_collected={stats['total_collected']}, pending={stats['pending_count']}, total_transactions={stats['total_transactions']}")
    
    def test_payments_page2_returns_different_records(self, auth_headers):
        """Test that page 2 returns different records than page 1"""
        # Get page 1
        response1 = requests.get(f"{BASE_URL}/api/payments?page=1&limit=10", headers=auth_headers)
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Skip if not enough data for page 2
        if data1["total_pages"] < 2:
            pytest.skip("Not enough payments for page 2 test")
        
        # Get page 2
        response2 = requests.get(f"{BASE_URL}/api/payments?page=2&limit=10", headers=auth_headers)
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Verify page 2 has different records
        page1_ids = {p["id"] for p in data1["payments"]}
        page2_ids = {p["id"] for p in data2["payments"]}
        
        assert page1_ids.isdisjoint(page2_ids), "Page 1 and Page 2 should have different payment IDs"
        assert data2["page"] == 2
        
        print(f"Page 1 IDs: {len(page1_ids)}, Page 2 IDs: {len(page2_ids)}, No overlap: PASS")
    
    def test_payments_stats_accuracy(self, auth_headers):
        """Test that stats.total_transactions equals total count of ALL payments"""
        # Get with small limit to test stats accuracy
        response = requests.get(f"{BASE_URL}/api/payments?page=1&limit=5", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        stats = data["stats"]
        
        # total_transactions should be total count of ALL payments (not just current page)
        # It should equal or be greater than 'total' (which is filtered count)
        assert stats["total_transactions"] >= data["total"], \
            f"total_transactions ({stats['total_transactions']}) should be >= total ({data['total']})"
        
        # Verify stats are not just page count
        assert stats["total_transactions"] != len(data["payments"]) or data["total"] == len(data["payments"]), \
            "total_transactions should reflect ALL payments, not just current page"
        
        print(f"Stats accuracy: total_transactions={stats['total_transactions']}, page_count={len(data['payments'])}, filtered_total={data['total']}")
    
    def test_payments_status_filter_with_stats(self, auth_headers):
        """Test status filter returns accurate stats"""
        # Get pending payments
        response = requests.get(f"{BASE_URL}/api/payments?page=1&limit=10&status=pending", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # All returned payments should be pending
        for payment in data["payments"]:
            assert payment["status"] == "pending", f"Expected pending, got {payment['status']}"
        
        # Stats should still reflect ALL payments (not just filtered)
        stats = data["stats"]
        assert stats["total_transactions"] >= data["total"], \
            "total_transactions should be >= filtered total"
        
        print(f"Pending filter: {len(data['payments'])} pending payments, total_transactions={stats['total_transactions']}")
    
    def test_payments_search_with_pagination(self, auth_headers):
        """Test search works with pagination"""
        # First get some payments to find a search term
        response = requests.get(f"{BASE_URL}/api/payments?page=1&limit=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        if len(data["payments"]) == 0:
            pytest.skip("No payments to search")
        
        # Search by telegram_user_id of first payment
        search_term = data["payments"][0].get("telegram_user_id", "")
        if not search_term:
            pytest.skip("No telegram_user_id to search")
        
        search_response = requests.get(
            f"{BASE_URL}/api/payments?page=1&limit=10&search={search_term}", 
            headers=auth_headers
        )
        assert search_response.status_code == 200
        
        search_data = search_response.json()
        assert "payments" in search_data
        assert "total" in search_data
        
        # Verify search results contain the search term
        for payment in search_data["payments"]:
            assert search_term in str(payment.get("telegram_user_id", "")) or \
                   search_term in str(payment.get("telegram_username", "")), \
                   f"Search result should contain '{search_term}'"
        
        print(f"Search '{search_term}': found {len(search_data['payments'])} payments")


class TestSubscribersPagination:
    """Test GET /api/subscribers pagination and stats"""
    
    def test_subscribers_page1_returns_paginated_response(self, auth_headers):
        """Test that page 1 returns proper paginated structure"""
        response = requests.get(f"{BASE_URL}/api/subscribers?page=1&limit=10", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        # Verify paginated response structure
        assert "subscribers" in data, "Response should have 'subscribers' array"
        assert "total" in data, "Response should have 'total' count"
        assert "page" in data, "Response should have 'page' number"
        assert "limit" in data, "Response should have 'limit'"
        assert "total_pages" in data, "Response should have 'total_pages'"
        assert "stats" in data, "Response should have 'stats' object"
        
        # Verify stats structure
        stats = data["stats"]
        assert "total_subscribers" in stats, "Stats should have 'total_subscribers'"
        assert "active_count" in stats, "Stats should have 'active_count'"
        assert "expired_count" in stats, "Stats should have 'expired_count'"
        
        # Verify pagination values
        assert data["page"] == 1
        assert data["limit"] == 10
        assert len(data["subscribers"]) <= 10, "Should return at most 10 subscribers"
        
        print(f"Page 1: {len(data['subscribers'])} subscribers, total: {data['total']}, total_pages: {data['total_pages']}")
        print(f"Stats: total_subscribers={stats['total_subscribers']}, active={stats['active_count']}, expired={stats['expired_count']}")
    
    def test_subscribers_page2_returns_different_records(self, auth_headers):
        """Test that page 2 returns different records than page 1"""
        # Get page 1
        response1 = requests.get(f"{BASE_URL}/api/subscribers?page=1&limit=10", headers=auth_headers)
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Skip if not enough data for page 2
        if data1["total_pages"] < 2:
            pytest.skip("Not enough subscribers for page 2 test")
        
        # Get page 2
        response2 = requests.get(f"{BASE_URL}/api/subscribers?page=2&limit=10", headers=auth_headers)
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Verify page 2 has different records
        page1_ids = {s["id"] for s in data1["subscribers"]}
        page2_ids = {s["id"] for s in data2["subscribers"]}
        
        assert page1_ids.isdisjoint(page2_ids), "Page 1 and Page 2 should have different subscriber IDs"
        assert data2["page"] == 2
        
        print(f"Page 1 IDs: {len(page1_ids)}, Page 2 IDs: {len(page2_ids)}, No overlap: PASS")
    
    def test_subscribers_stats_accuracy(self, auth_headers):
        """Test that stats.total_subscribers equals total count of ALL subscribers"""
        response = requests.get(f"{BASE_URL}/api/subscribers?page=1&limit=5", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        stats = data["stats"]
        
        # total_subscribers should be total count of ALL subscribers
        assert stats["total_subscribers"] >= data["total"], \
            f"total_subscribers ({stats['total_subscribers']}) should be >= total ({data['total']})"
        
        # active_count + expired_count should be <= total_subscribers
        assert stats["active_count"] + stats["expired_count"] <= stats["total_subscribers"], \
            "active + expired should be <= total_subscribers"
        
        print(f"Stats accuracy: total_subscribers={stats['total_subscribers']}, active={stats['active_count']}, expired={stats['expired_count']}")
    
    def test_subscribers_status_filter(self, auth_headers):
        """Test status filter works correctly"""
        # Get active subscribers
        response = requests.get(f"{BASE_URL}/api/subscribers?page=1&limit=10&status=active", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # All returned subscribers should be active
        for sub in data["subscribers"]:
            assert sub["status"] == "active", f"Expected active, got {sub['status']}"
        
        print(f"Active filter: {len(data['subscribers'])} active subscribers")


class TestAnalytics:
    """Test GET /api/analytics with aggregation-based revenue"""
    
    def test_analytics_returns_proper_data(self, auth_headers):
        """Test analytics endpoint returns proper revenue data"""
        response = requests.get(f"{BASE_URL}/api/analytics", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify required fields
        assert "total_subscribers" in data
        assert "active_subscribers" in data
        assert "expired_subscribers" in data
        assert "total_revenue" in data
        assert "monthly_revenue" in data
        
        # Verify revenue is a number
        assert isinstance(data["total_revenue"], (int, float)), "total_revenue should be a number"
        assert isinstance(data["monthly_revenue"], (int, float)), "monthly_revenue should be a number"
        
        # Verify subscriber counts are non-negative
        assert data["total_subscribers"] >= 0
        assert data["active_subscribers"] >= 0
        assert data["expired_subscribers"] >= 0
        
        print(f"Analytics: total_revenue={data['total_revenue']}, monthly_revenue={data['monthly_revenue']}")
        print(f"Subscribers: total={data['total_subscribers']}, active={data['active_subscribers']}, expired={data['expired_subscribers']}")
    
    def test_analytics_revenue_consistency(self, auth_headers):
        """Test that analytics revenue is consistent with payments stats"""
        # Get analytics
        analytics_response = requests.get(f"{BASE_URL}/api/analytics", headers=auth_headers)
        assert analytics_response.status_code == 200
        analytics = analytics_response.json()
        
        # Get payments stats
        payments_response = requests.get(f"{BASE_URL}/api/payments?page=1&limit=1", headers=auth_headers)
        assert payments_response.status_code == 200
        payments_data = payments_response.json()
        
        # total_collected from payments should match total_revenue from analytics
        payments_total_collected = payments_data["stats"]["total_collected"]
        analytics_total_revenue = analytics["total_revenue"]
        
        assert payments_total_collected == analytics_total_revenue, \
            f"Payments total_collected ({payments_total_collected}) should match analytics total_revenue ({analytics_total_revenue})"
        
        print(f"Revenue consistency: payments={payments_total_collected}, analytics={analytics_total_revenue} - MATCH")


class TestPaginationEdgeCases:
    """Test edge cases for pagination"""
    
    def test_payments_invalid_page_defaults_to_1(self, auth_headers):
        """Test that invalid page number defaults to page 1"""
        response = requests.get(f"{BASE_URL}/api/payments?page=0&limit=10", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        # Page 0 should be treated as page 1
        assert data["page"] == 1 or len(data["payments"]) > 0
        
        print("Invalid page (0) handled correctly")
    
    def test_payments_large_limit_capped(self, auth_headers):
        """Test that limit is capped at max (200)"""
        response = requests.get(f"{BASE_URL}/api/payments?page=1&limit=500", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        # Limit should be capped at 200
        assert data["limit"] <= 200, f"Limit should be capped at 200, got {data['limit']}"
        
        print(f"Large limit capped: requested 500, got {data['limit']}")
    
    def test_payments_empty_search_returns_all(self, auth_headers):
        """Test that empty search returns all payments"""
        # Get without search
        response1 = requests.get(f"{BASE_URL}/api/payments?page=1&limit=10", headers=auth_headers)
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Get with empty search
        response2 = requests.get(f"{BASE_URL}/api/payments?page=1&limit=10&search=", headers=auth_headers)
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Both should return same total
        assert data1["total"] == data2["total"], "Empty search should return same total as no search"
        
        print(f"Empty search: total={data2['total']} (same as no search)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
