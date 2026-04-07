"""
Iteration 37: Phase 2+3 Testing - Role-Based Guards, Impersonation, Risk & Alerts
Tests:
- Super Admin login (role-based only, no email bypass)
- Tenant Admin login (correctly scoped)
- Impersonation API (POST /api/saas/impersonate/{tenant_id})
- Impersonation Audit Log (GET /api/saas/impersonation-log)
- Risk Alerts API (GET /api/saas/risk-alerts)
- Dismiss Alert API (POST /api/saas/risk-alerts/{alert_id}/dismiss)
- Tenant Admin cannot access Super Admin APIs (403)
- JWT token includes role and tenant_id
- X-Request-ID header present in all responses
"""
import pytest
import requests
import os
import base64
import json

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from test_credentials.md
SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"
SUPER_ADMIN_PASSWORD = "Sumit@8958"
TENANT_ADMIN_EMAIL = "anamika@test.com"
TENANT_ADMIN_PASSWORD = "Admin123"


class TestSuperAdminAuth:
    """Super Admin authentication - role-based only"""
    
    def test_super_admin_login_success(self):
        """Super Admin login returns role='super_admin'"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        assert "user" in data, "No user in response"
        assert data["user"]["role"] == "super_admin", f"Expected role='super_admin', got {data['user'].get('role')}"
        print(f"PASS: Super Admin login returns role='super_admin'")
    
    def test_super_admin_jwt_contains_role_and_tenant_id(self):
        """JWT token contains role and tenant_id fields"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["token"]
        
        # Decode JWT payload (base64)
        parts = token.split(".")
        assert len(parts) == 3, "Invalid JWT format"
        payload_b64 = parts[1]
        # Add padding if needed
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        
        assert "role" in payload, "JWT missing 'role' field"
        assert "tenant_id" in payload, "JWT missing 'tenant_id' field"
        assert payload["role"] == "super_admin", f"JWT role mismatch: {payload['role']}"
        print(f"PASS: JWT contains role='{payload['role']}' and tenant_id='{payload.get('tenant_id', '')}'")
    
    def test_check_admin_returns_super_admin_role(self):
        """GET /api/auth/check-admin returns is_admin=true, role=super_admin"""
        # Login first
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        token = login_resp.json()["token"]
        
        response = requests.get(f"{BASE_URL}/api/auth/check-admin", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("is_admin") == True, f"Expected is_admin=True, got {data.get('is_admin')}"
        assert data.get("role") == "super_admin", f"Expected role='super_admin', got {data.get('role')}"
        print(f"PASS: check-admin returns is_admin=True, role='super_admin'")


class TestTenantAdminAuth:
    """Tenant Admin authentication - correctly scoped"""
    
    def test_tenant_admin_login_success(self):
        """Tenant Admin login returns role='tenant_admin'"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        assert data["user"]["role"] == "tenant_admin", f"Expected role='tenant_admin', got {data['user'].get('role')}"
        assert "tenant_id" in data["user"], "No tenant_id in user response"
        print(f"PASS: Tenant Admin login returns role='tenant_admin', tenant_id='{data['user'].get('tenant_id')}'")
    
    def test_tenant_admin_jwt_contains_role_and_tenant_id(self):
        """Tenant Admin JWT contains role='tenant_admin' and tenant_id"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["token"]
        
        # Decode JWT payload
        parts = token.split(".")
        payload_b64 = parts[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        
        assert payload.get("role") == "tenant_admin", f"JWT role mismatch: {payload.get('role')}"
        assert payload.get("tenant_id"), "JWT missing tenant_id"
        print(f"PASS: Tenant Admin JWT has role='tenant_admin', tenant_id='{payload.get('tenant_id')}'")
    
    def test_tenant_admin_denied_super_admin_endpoints(self):
        """Tenant Admin gets 403 on Super Admin endpoints"""
        # Login as tenant admin
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        token = login_resp.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test super admin endpoints
        super_admin_endpoints = [
            ("GET", "/api/saas/tenants"),
            ("GET", "/api/tenant-users"),
            ("GET", "/api/admin/stats"),
            ("GET", "/api/trial/config"),
            ("GET", "/api/saas/risk-alerts"),
        ]
        
        for method, endpoint in super_admin_endpoints:
            if method == "GET":
                resp = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
            else:
                resp = requests.post(f"{BASE_URL}{endpoint}", headers=headers, json={})
            
            assert resp.status_code == 403, f"Expected 403 for {endpoint}, got {resp.status_code}"
            print(f"PASS: Tenant Admin denied access to {endpoint} (403)")


class TestImpersonationAPI:
    """Impersonation Mode - Super Admin can impersonate Tenant Admin"""
    
    @pytest.fixture
    def super_admin_token(self):
        """Get super admin token"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        return resp.json()["token"]
    
    def test_impersonate_tenant_returns_token(self, super_admin_token):
        """POST /api/saas/impersonate/{tenant_id} returns impersonated token"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        
        # First get a tenant to impersonate
        tenants_resp = requests.get(f"{BASE_URL}/api/saas/tenants", headers=headers)
        assert tenants_resp.status_code == 200
        tenants = tenants_resp.json()
        
        if not tenants:
            pytest.skip("No tenants available to impersonate")
        
        tenant_id = tenants[0]["tenant_id"]
        
        # Impersonate
        resp = requests.post(f"{BASE_URL}/api/saas/impersonate/{tenant_id}", headers=headers, json={})
        assert resp.status_code == 200, f"Impersonation failed: {resp.text}"
        
        data = resp.json()
        assert "token" in data, "No token in impersonation response"
        assert "user" in data, "No user in impersonation response"
        assert data["user"].get("tenant_id") == tenant_id, "Impersonated user has wrong tenant_id"
        assert data["user"].get("role") in ["tenant_admin", "tenant_owner"], f"Unexpected role: {data['user'].get('role')}"
        print(f"PASS: Impersonation returns token for tenant {tenant_id}")
    
    def test_impersonate_nonexistent_tenant_returns_404(self, super_admin_token):
        """Impersonating non-existent tenant returns 404"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        resp = requests.post(f"{BASE_URL}/api/saas/impersonate/nonexistent_tenant_xyz", headers=headers, json={})
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("PASS: Impersonating non-existent tenant returns 404")
    
    def test_impersonation_audit_log(self, super_admin_token):
        """GET /api/saas/impersonation-log returns log entries"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/saas/impersonation-log", headers=headers)
        assert resp.status_code == 200, f"Failed to get impersonation log: {resp.text}"
        
        logs = resp.json()
        assert isinstance(logs, list), "Impersonation log should be a list"
        print(f"PASS: Impersonation log returns {len(logs)} entries")


class TestRiskAlertsAPI:
    """Risk & Alerts System - Fraud detection and anomaly monitoring"""
    
    @pytest.fixture
    def super_admin_token(self):
        """Get super admin token"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        return resp.json()["token"]
    
    def test_risk_alerts_returns_structure(self, super_admin_token):
        """GET /api/saas/risk-alerts returns proper structure"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/saas/risk-alerts", headers=headers)
        assert resp.status_code == 200, f"Failed to get risk alerts: {resp.text}"
        
        data = resp.json()
        assert "alerts" in data, "Missing 'alerts' field"
        assert "total" in data, "Missing 'total' field"
        assert "critical_count" in data, "Missing 'critical_count' field"
        assert "warning_count" in data, "Missing 'warning_count' field"
        assert "info_count" in data, "Missing 'info_count' field"
        
        assert isinstance(data["alerts"], list), "'alerts' should be a list"
        assert isinstance(data["total"], int), "'total' should be an integer"
        print(f"PASS: Risk alerts returns proper structure (total={data['total']}, critical={data['critical_count']}, warning={data['warning_count']}, info={data['info_count']})")
    
    def test_dismiss_alert_api(self, super_admin_token):
        """POST /api/saas/risk-alerts/{alert_id}/dismiss works"""
        headers = {"Authorization": f"Bearer {super_admin_token}", "Content-Type": "application/json"}
        
        # Try to dismiss a test alert (even if it doesn't exist, API should handle gracefully)
        resp = requests.post(
            f"{BASE_URL}/api/saas/risk-alerts/test_alert_123/dismiss",
            headers=headers,
            json={"reason": "Test dismissal"}
        )
        # Should return 200 (alert dismissed) - the API creates a dismissal record
        assert resp.status_code == 200, f"Dismiss alert failed: {resp.text}"
        data = resp.json()
        assert "message" in data, "No message in dismiss response"
        print("PASS: Dismiss alert API works")


class TestRequestContextMiddleware:
    """X-Request-ID header present in all API responses"""
    
    def test_x_request_id_in_login_response(self):
        """Login response includes X-Request-ID header"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert "X-Request-ID" in resp.headers, "Missing X-Request-ID header"
        request_id = resp.headers["X-Request-ID"]
        # Validate UUID format
        assert len(request_id) == 36, f"Invalid X-Request-ID format: {request_id}"
        print(f"PASS: X-Request-ID header present: {request_id}")
    
    def test_x_request_id_unique_per_request(self):
        """Each request gets a unique X-Request-ID"""
        ids = set()
        for _ in range(3):
            resp = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": SUPER_ADMIN_EMAIL,
                "password": SUPER_ADMIN_PASSWORD
            })
            ids.add(resp.headers.get("X-Request-ID"))
        
        assert len(ids) == 3, f"X-Request-IDs not unique: {ids}"
        print("PASS: X-Request-ID is unique per request")


class TestSuperAdminDashboardEndpoints:
    """Super Admin can access dashboard endpoints"""
    
    @pytest.fixture
    def super_admin_token(self):
        """Get super admin token"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        return resp.json()["token"]
    
    def test_admin_stats_endpoint(self, super_admin_token):
        """GET /api/admin/stats returns platform stats"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/admin/stats", headers=headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "platform" in data, "Missing 'platform' stats"
        assert "bot_ecosystem" in data, "Missing 'bot_ecosystem' stats"
        assert "revenue" in data, "Missing 'revenue' stats"
        print("PASS: /api/admin/stats returns platform stats")
    
    def test_saas_tenants_endpoint(self, super_admin_token):
        """GET /api/saas/tenants returns tenant list"""
        headers = {"Authorization": f"Bearer {super_admin_token}"}
        resp = requests.get(f"{BASE_URL}/api/saas/tenants", headers=headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        tenants = resp.json()
        assert isinstance(tenants, list), "Tenants should be a list"
        print(f"PASS: /api/saas/tenants returns {len(tenants)} tenants")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
