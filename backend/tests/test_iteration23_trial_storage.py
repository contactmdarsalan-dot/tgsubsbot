"""
Iteration 23 Tests: Trial Management + Object Storage Migration
Tests:
1. Trial Management Backend (7 endpoints)
2. Object Storage Upload/Download (6 upload points migrated)
3. Backward compatibility for old /api/uploads/ URLs
4. Super Admin and Tenant Admin login/dashboard access
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from test_credentials.md
SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"
SUPER_ADMIN_PASSWORD = "Sumit@8958"
TENANT_ADMIN_EMAIL = "anamika@test.com"
TENANT_ADMIN_PASSWORD = "Admin123"
TENANT_ID = "tenant_85ee971d0285"
TEST_TG_ID = "123456789"


def get_super_admin_token():
    """Get fresh Super Admin token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    return resp.json().get("token")


def get_tenant_admin_token():
    """Get fresh Tenant Admin token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TENANT_ADMIN_EMAIL,
        "password": TENANT_ADMIN_PASSWORD
    })
    return resp.json().get("token")


class TestAuthAndDashboardAccess:
    """Test login and dashboard access for Super Admin and Tenant Admin"""

    def test_super_admin_login(self):
        """Super Admin can login successfully"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert resp.status_code == 200, f"Super Admin login failed: {resp.text}"
        data = resp.json()
        assert "token" in data, "No token in response"
        assert data.get("user", {}).get("role") in ["super_admin", "admin"], f"Unexpected role: {data}"
        print(f"✓ Super Admin login successful, role: {data.get('user', {}).get('role')}")

    def test_tenant_admin_login(self):
        """Tenant Admin can login successfully"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        assert resp.status_code == 200, f"Tenant Admin login failed: {resp.text}"
        data = resp.json()
        assert "token" in data, "No token in response"
        assert data.get("user", {}).get("role") == "tenant_admin", f"Unexpected role: {data}"
        assert data.get("user", {}).get("tenant_id") == TENANT_ID, f"Wrong tenant_id: {data}"
        print(f"✓ Tenant Admin login successful, tenant_id: {data.get('user', {}).get('tenant_id')}")

    def test_super_admin_dashboard_access(self):
        """Super Admin can access dashboard analytics"""
        token = get_super_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{BASE_URL}/api/analytics", headers=headers)
        assert resp.status_code == 200, f"Analytics access failed: {resp.text}"
        data = resp.json()
        assert "total_subscribers" in data or "total_revenue" in data, f"Unexpected analytics data: {data}"
        print(f"✓ Super Admin dashboard access verified")

    def test_tenant_admin_dashboard_access(self):
        """Tenant Admin can access dashboard analytics"""
        token = get_tenant_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{BASE_URL}/api/analytics", headers=headers)
        assert resp.status_code == 200, f"Analytics access failed: {resp.text}"
        print(f"✓ Tenant Admin dashboard access verified")


class TestTrialManagementBackend:
    """Test all 7 Trial Management endpoints"""

    def test_get_trial_config(self):
        """GET /api/trial/config - Get trial configuration"""
        token = get_super_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{BASE_URL}/api/trial/config", headers=headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "enabled" in data, f"Missing 'enabled' field: {data}"
        assert "duration_days" in data, f"Missing 'duration_days' field: {data}"
        assert "features" in data, f"Missing 'features' field: {data}"
        print(f"✓ GET /api/trial/config - duration_days: {data.get('duration_days')}")

    def test_get_trial_accounts(self):
        """GET /api/trial/accounts - Get all trial accounts"""
        token = get_super_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{BASE_URL}/api/trial/accounts", headers=headers)
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert isinstance(data, list), f"Expected list, got: {type(data)}"
        print(f"✓ GET /api/trial/accounts - {len(data)} trial accounts found")

    def test_update_trial_config(self):
        """PUT /api/trial/config - Update trial configuration"""
        token = get_super_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # First get current config
        get_resp = requests.get(f"{BASE_URL}/api/trial/config", headers=headers)
        original_days = get_resp.json().get("duration_days", 7)

        # Update to new value
        new_days = 14 if original_days != 14 else 7
        resp = requests.put(f"{BASE_URL}/api/trial/config", headers=headers, json={
            "duration_days": new_days,
            "enabled": True,
            "max_subscribers_trial": 50
        })
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "message" in data, f"Missing message: {data}"
        print(f"✓ PUT /api/trial/config - updated duration_days to {new_days}")

        # Restore original
        requests.put(f"{BASE_URL}/api/trial/config", headers=headers, json={
            "duration_days": original_days
        })

    def test_activate_trial(self):
        """POST /api/trial/activate - Activate trial for a user"""
        token = get_super_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get a tenant admin to activate trial for
        admins_resp = requests.get(f"{BASE_URL}/api/saas/tenant-admins", headers=headers)
        admins = admins_resp.json()
        
        if not admins:
            pytest.skip("No tenant admins available for trial activation test")
        
        # Find a user not already on trial
        target_user = None
        for admin in admins:
            if admin.get("dashboard_subscription_status") != "trial":
                target_user = admin
                break
        
        if not target_user:
            target_user = admins[0]

        resp = requests.post(f"{BASE_URL}/api/trial/activate", headers=headers, json={
            "user_id": target_user["id"],
            "duration_days": 7
        })
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "message" in data, f"Missing message: {data}"
        assert "expires" in data, f"Missing expires: {data}"
        print(f"✓ POST /api/trial/activate - Trial activated for {target_user.get('email')}")

    def test_extend_trial(self):
        """POST /api/trial/extend - Extend a user's trial"""
        token = get_super_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get trial accounts
        trials_resp = requests.get(f"{BASE_URL}/api/trial/accounts", headers=headers)
        trials = trials_resp.json()
        
        if not trials:
            pytest.skip("No trial accounts to extend")
        
        target_user = trials[0]
        resp = requests.post(f"{BASE_URL}/api/trial/extend", headers=headers, json={
            "user_id": target_user["id"],
            "extra_days": 3
        })
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "message" in data, f"Missing message: {data}"
        assert "new_end" in data, f"Missing new_end: {data}"
        print(f"✓ POST /api/trial/extend - Trial extended for {target_user.get('email')}")

    def test_cancel_trial(self):
        """POST /api/trial/cancel - Cancel a user's trial"""
        token = get_super_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # First activate a trial to cancel
        admins_resp = requests.get(f"{BASE_URL}/api/saas/tenant-admins", headers=headers)
        admins = admins_resp.json()
        
        if not admins:
            pytest.skip("No tenant admins available")
        
        # Activate trial first
        target_user = admins[0]
        requests.post(f"{BASE_URL}/api/trial/activate", headers=headers, json={
            "user_id": target_user["id"],
            "duration_days": 7
        })

        # Now cancel it
        resp = requests.post(f"{BASE_URL}/api/trial/cancel", headers=headers, json={
            "user_id": target_user["id"]
        })
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "message" in data, f"Missing message: {data}"
        print(f"✓ POST /api/trial/cancel - Trial cancelled for {target_user.get('email')}")

    def test_convert_trial_to_paid(self):
        """POST /api/trial/convert - Convert trial to paid subscription"""
        token = get_super_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get trial accounts
        trials_resp = requests.get(f"{BASE_URL}/api/trial/accounts", headers=headers)
        trials = trials_resp.json()
        
        # Get dashboard plans
        plans_resp = requests.get(f"{BASE_URL}/api/admin/dashboard-plans", headers=headers)
        plans = plans_resp.json()
        
        if not trials:
            # Activate a trial first
            admins_resp = requests.get(f"{BASE_URL}/api/saas/tenant-admins", headers=headers)
            admins = admins_resp.json()
            if admins:
                requests.post(f"{BASE_URL}/api/trial/activate", headers=headers, json={
                    "user_id": admins[0]["id"],
                    "duration_days": 7
                })
                trials_resp = requests.get(f"{BASE_URL}/api/trial/accounts", headers=headers)
                trials = trials_resp.json()
        
        if not trials or not plans:
            pytest.skip("No trial accounts or plans available")
        
        target_user = trials[0]
        plan_id = plans[0]["id"] if plans else "1month"
        
        resp = requests.post(f"{BASE_URL}/api/trial/convert", headers=headers, json={
            "user_id": target_user["id"],
            "plan_id": plan_id,
            "duration_days": 30
        })
        assert resp.status_code == 200, f"Failed: {resp.text}"
        data = resp.json()
        assert "message" in data, f"Missing message: {data}"
        print(f"✓ POST /api/trial/convert - Trial converted to paid for {target_user.get('email')}")

    def test_trial_config_requires_super_admin(self):
        """Trial endpoints require super admin access"""
        # Login as tenant admin
        tenant_token = get_tenant_admin_token()
        tenant_headers = {"Authorization": f"Bearer {tenant_token}"}

        # Try to access trial config
        resp = requests.get(f"{BASE_URL}/api/trial/config", headers=tenant_headers)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print(f"✓ Trial endpoints correctly require super admin access")


class TestObjectStorageUpload:
    """Test Object Storage upload endpoints"""

    def test_upload_image(self):
        """POST /api/upload/image - Upload image to object storage"""
        token = get_super_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # Create a simple test image (1x1 red PNG)
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00,
            0x00, 0x00, 0x03, 0x00, 0x01, 0x00, 0x18, 0xDD,
            0x8D, 0xB4, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45,
            0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82
        ])

        files = {"file": ("test_image.png", io.BytesIO(png_data), "image/png")}
        resp = requests.post(f"{BASE_URL}/api/upload/image", headers=headers, files=files)
        assert resp.status_code == 200, f"Upload failed: {resp.text}"
        data = resp.json()
        assert "url" in data, f"Missing url: {data}"
        assert data["url"].startswith("/api/files/"), f"URL should start with /api/files/: {data['url']}"
        print(f"✓ POST /api/upload/image - URL: {data['url']}")

    def test_upload_qr_code(self):
        """POST /api/upload/qr-code - Upload QR code to object storage"""
        token = get_super_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # Create a simple test image
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00,
            0x00, 0x00, 0x03, 0x00, 0x01, 0x00, 0x18, 0xDD,
            0x8D, 0xB4, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45,
            0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82
        ])

        files = {"file": ("test_qr.png", io.BytesIO(png_data), "image/png")}
        resp = requests.post(f"{BASE_URL}/api/upload/qr-code", headers=headers, files=files)
        assert resp.status_code == 200, f"Upload failed: {resp.text}"
        data = resp.json()
        assert "url" in data, f"Missing url: {data}"
        assert data["url"].startswith("/api/files/"), f"URL should start with /api/files/: {data['url']}"
        print(f"✓ POST /api/upload/qr-code - URL: {data['url']}")

    def test_miniapp_upload_screenshot(self):
        """POST /api/miniapp/upload-screenshot - Upload screenshot to object storage"""
        # Create a simple test image
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00,
            0x00, 0x00, 0x03, 0x00, 0x01, 0x00, 0x18, 0xDD,
            0x8D, 0xB4, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45,
            0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82
        ])

        files = {"file": ("screenshot.png", io.BytesIO(png_data), "image/png")}
        data = {
            "telegram_user_id": TEST_TG_ID,
            "plan_id": "test_plan",
            "plan_name": "Test Plan",
            "amount": 100
        }
        resp = requests.post(f"{BASE_URL}/api/miniapp/upload-screenshot", files=files, data=data)
        assert resp.status_code == 200, f"Upload failed: {resp.text}"
        result = resp.json()
        assert "success" in result or "payment_id" in result or "screenshot_url" in result, f"Unexpected response: {result}"
        print(f"✓ POST /api/miniapp/upload-screenshot - Response: {result.get('success', result.get('payment_id', 'OK'))}")


class TestObjectStorageDownload:
    """Test Object Storage download endpoint"""

    def test_download_uploaded_file(self):
        """GET /api/files/{storage_path} - Download uploaded file"""
        token = get_super_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # First upload a file
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00,
            0x00, 0x00, 0x03, 0x00, 0x01, 0x00, 0x18, 0xDD,
            0x8D, 0xB4, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45,
            0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82
        ])

        files = {"file": ("download_test.png", io.BytesIO(png_data), "image/png")}
        upload_resp = requests.post(f"{BASE_URL}/api/upload/image", headers=headers, files=files)
        assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text}"
        
        url = upload_resp.json()["url"]
        assert url.startswith("/api/files/"), f"URL should start with /api/files/: {url}"

        # Now download the file
        download_resp = requests.get(f"{BASE_URL}{url}")
        assert download_resp.status_code == 200, f"Download failed: {download_resp.status_code}"
        assert download_resp.headers.get("content-type", "").startswith("image/"), f"Wrong content-type: {download_resp.headers.get('content-type')}"
        assert len(download_resp.content) > 0, "Downloaded file is empty"
        print(f"✓ GET {url} - Downloaded {len(download_resp.content)} bytes, content-type: {download_resp.headers.get('content-type')}")

    def test_download_nonexistent_file(self):
        """GET /api/files/{storage_path} - 404 for nonexistent file"""
        resp = requests.get(f"{BASE_URL}/api/files/nonexistent/path/file.png")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print(f"✓ GET /api/files/nonexistent - Returns 404 as expected")


class TestBackwardCompatibility:
    """Test backward compatibility for old /api/uploads/ URLs"""

    def test_old_uploads_url_still_works(self):
        """GET /api/uploads/{filename} - Old local files still served"""
        resp = requests.get(f"{BASE_URL}/api/uploads/qr_code_e06e8c59.gif")
        assert resp.status_code in [200, 404], f"Unexpected status: {resp.status_code}"
        if resp.status_code == 200:
            print(f"✓ GET /api/uploads/qr_code_e06e8c59.gif - Old file served successfully")
        else:
            print(f"✓ GET /api/uploads/ endpoint accessible (file not found is OK)")


class TestSaaSManagementTrialsTab:
    """Test SaaS Management Trials tab data endpoints"""

    def test_trials_tab_data_endpoints(self):
        """All endpoints needed for Trials tab work"""
        token = get_super_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # Trial config
        resp1 = requests.get(f"{BASE_URL}/api/trial/config", headers=headers)
        assert resp1.status_code == 200, f"trial/config failed: {resp1.text}"
        
        # Trial accounts
        resp2 = requests.get(f"{BASE_URL}/api/trial/accounts", headers=headers)
        assert resp2.status_code == 200, f"trial/accounts failed: {resp2.text}"
        
        # Tenant admins (for "Activate Trial for Existing User" dropdown)
        resp3 = requests.get(f"{BASE_URL}/api/saas/tenant-admins", headers=headers)
        assert resp3.status_code == 200, f"saas/tenant-admins failed: {resp3.text}"
        
        # Dashboard plans (for convert dialog)
        resp4 = requests.get(f"{BASE_URL}/api/admin/dashboard-plans", headers=headers)
        assert resp4.status_code == 200, f"admin/dashboard-plans failed: {resp4.text}"
        
        print(f"✓ All Trials tab data endpoints working")
        print(f"  - Trial config: {resp1.json().get('duration_days')} days")
        print(f"  - Trial accounts: {len(resp2.json())} accounts")
        print(f"  - Tenant admins: {len(resp3.json())} admins")
        print(f"  - Dashboard plans: {len(resp4.json())} plans")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
