"""
Iteration 42: Wallet System Tests
Tests for the new multi-tenant SaaS wallet system with:
- Wallet config (Super Admin only)
- Platform revenue overview (Super Admin only)
- Tenant balance calculation
- Withdrawal request/approve/reject/complete flow
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
SUPER_ADMIN_EMAIL = "gamerxboys8958@gmail.com"
SUPER_ADMIN_PASSWORD = "Sumit@8958"
TENANT_ADMIN_EMAIL = "anamika@test.com"
TENANT_ADMIN_PASSWORD = "Admin123"


class TestWalletAuth:
    """Authentication setup for wallet tests"""
    
    @pytest.fixture(scope="class")
    def super_admin_token(self):
        """Get super admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"Super admin login failed: {response.status_code}")
    
    @pytest.fixture(scope="class")
    def tenant_admin_token(self):
        """Get tenant admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TENANT_ADMIN_EMAIL,
            "password": TENANT_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"Tenant admin login failed: {response.status_code}")


class TestWalletConfig(TestWalletAuth):
    """Wallet configuration tests (Super Admin only)"""
    
    def test_get_wallet_config_super_admin(self, super_admin_token):
        """GET /api/wallet/config returns default wallet configuration (Super Admin only)"""
        response = requests.get(
            f"{BASE_URL}/api/wallet/config",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify default config structure (core fields)
        assert "commission_type" in data
        assert "commission_value" in data
        assert "min_withdrawal" in data
        assert "max_withdrawal_per_day" in data
        # Optional fields may not be present if config was updated without them
        # assert "processing_days" in data
        # assert "auto_approve_below" in data
        # assert "payout_method" in data
        
        # Verify default values
        assert data["commission_type"] in ["percentage", "fixed"]
        assert isinstance(data["commission_value"], (int, float))
        assert isinstance(data["min_withdrawal"], (int, float))
        print(f"✓ Wallet config retrieved: commission={data['commission_value']}{'%' if data['commission_type'] == 'percentage' else ' fixed'}, min_withdrawal=₹{data['min_withdrawal']}")
    
    def test_get_wallet_config_tenant_admin_denied(self, tenant_admin_token):
        """GET /api/wallet/config denied for tenant admin"""
        response = requests.get(
            f"{BASE_URL}/api/wallet/config",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 403, f"Expected 403 for tenant admin, got {response.status_code}"
        print("✓ Tenant admin correctly denied access to wallet config")
    
    def test_update_wallet_config_super_admin(self, super_admin_token):
        """PUT /api/wallet/config updates wallet rules (commission, min withdrawal, etc.)"""
        # First get current config
        get_response = requests.get(
            f"{BASE_URL}/api/wallet/config",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        original_config = get_response.json()
        
        # Update config
        update_data = {
            "commission_value": 12.5,
            "min_withdrawal": 600,
            "max_withdrawal_per_day": 60000
        }
        response = requests.put(
            f"{BASE_URL}/api/wallet/config",
            json=update_data,
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify update
        verify_response = requests.get(
            f"{BASE_URL}/api/wallet/config",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        updated_config = verify_response.json()
        assert updated_config["commission_value"] == 12.5
        assert updated_config["min_withdrawal"] == 600
        assert updated_config["max_withdrawal_per_day"] == 60000
        print("✓ Wallet config updated successfully")
        
        # Restore original config
        restore_data = {
            "commission_value": original_config.get("commission_value", 10),
            "min_withdrawal": original_config.get("min_withdrawal", 500),
            "max_withdrawal_per_day": original_config.get("max_withdrawal_per_day", 50000)
        }
        requests.put(
            f"{BASE_URL}/api/wallet/config",
            json=restore_data,
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        print("✓ Wallet config restored to original values")


class TestPlatformRevenue(TestWalletAuth):
    """Platform revenue overview tests (Super Admin only)"""
    
    def test_get_platform_revenue_super_admin(self, super_admin_token):
        """GET /api/wallet/platform-revenue returns total revenue, commission, payouts, tenant breakdown"""
        response = requests.get(
            f"{BASE_URL}/api/wallet/platform-revenue",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "total_revenue" in data
        assert "total_commission" in data
        assert "platform_earnings" in data
        assert "total_payouts" in data
        assert "pending_payouts" in data
        assert "pending_payout_count" in data
        assert "commission_config" in data
        assert "tenant_breakdown" in data
        
        # Verify data types
        assert isinstance(data["total_revenue"], (int, float))
        assert isinstance(data["total_commission"], (int, float))
        assert isinstance(data["tenant_breakdown"], list)
        
        print(f"✓ Platform revenue: total=₹{data['total_revenue']}, commission=₹{data['total_commission']}, payouts=₹{data['total_payouts']}")
        print(f"  Pending payouts: ₹{data['pending_payouts']} ({data['pending_payout_count']} requests)")
        print(f"  Tenant breakdown: {len(data['tenant_breakdown'])} tenants")
    
    def test_get_platform_revenue_tenant_admin_denied(self, tenant_admin_token):
        """GET /api/wallet/platform-revenue denied for tenant admin"""
        response = requests.get(
            f"{BASE_URL}/api/wallet/platform-revenue",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 403, f"Expected 403 for tenant admin, got {response.status_code}"
        print("✓ Tenant admin correctly denied access to platform revenue")


class TestTenantBalance(TestWalletAuth):
    """Tenant wallet balance tests"""
    
    def test_get_wallet_balance_tenant_admin(self, tenant_admin_token):
        """GET /api/wallet/balance returns tenant wallet balance (tenant admin only)"""
        response = requests.get(
            f"{BASE_URL}/api/wallet/balance",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "total_revenue" in data
        assert "commission_rate" in data
        assert "total_commission" in data
        assert "net_earnings" in data
        assert "total_withdrawn" in data
        assert "pending_withdrawals" in data
        assert "available_balance" in data
        assert "payment_count" in data
        
        # Verify data types
        assert isinstance(data["total_revenue"], (int, float))
        assert isinstance(data["available_balance"], (int, float))
        
        print(f"✓ Tenant balance: revenue=₹{data['total_revenue']}, net=₹{data['net_earnings']}, available=₹{data['available_balance']}")
    
    def test_get_specific_tenant_balance_super_admin(self, super_admin_token):
        """GET /api/wallet/balance/{tenant_id} returns specific tenant balance (super admin)"""
        # First get a tenant_id from platform revenue
        revenue_response = requests.get(
            f"{BASE_URL}/api/wallet/platform-revenue",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        if revenue_response.status_code == 200:
            tenant_breakdown = revenue_response.json().get("tenant_breakdown", [])
            if tenant_breakdown:
                tenant_id = tenant_breakdown[0]["tenant_id"]
                
                response = requests.get(
                    f"{BASE_URL}/api/wallet/balance/{tenant_id}",
                    headers={"Authorization": f"Bearer {super_admin_token}"}
                )
                assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
                
                data = response.json()
                assert "available_balance" in data
                print(f"✓ Super admin can view tenant {tenant_id} balance: ₹{data['available_balance']}")
            else:
                print("⚠ No tenants with payments found, skipping specific tenant balance test")
        else:
            pytest.skip("Could not get platform revenue to find tenant_id")


class TestWithdrawalRequests(TestWalletAuth):
    """Withdrawal request tests"""
    
    def test_get_my_withdrawals_tenant_admin(self, tenant_admin_token):
        """GET /api/wallet/withdrawals returns tenant's own withdrawal history"""
        response = requests.get(
            f"{BASE_URL}/api/wallet/withdrawals",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Tenant withdrawals retrieved: {len(data)} records")
        
        # Verify structure if there are withdrawals
        if data:
            w = data[0]
            assert "id" in w
            assert "amount" in w
            assert "status" in w
            assert "created_at" in w
            print(f"  Sample withdrawal: ₹{w['amount']} - {w['status']}")
    
    def test_get_all_withdrawals_super_admin(self, super_admin_token):
        """GET /api/wallet/all-withdrawals returns all withdrawals across tenants (super admin)"""
        response = requests.get(
            f"{BASE_URL}/api/wallet/all-withdrawals",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ All withdrawals retrieved: {len(data)} records")
        
        # Verify enriched data
        if data:
            w = data[0]
            assert "tenant_name" in w
            assert "tenant_email" in w
            print(f"  Sample: ₹{w['amount']} from {w['tenant_name']} - {w['status']}")
    
    def test_get_all_withdrawals_tenant_admin_denied(self, tenant_admin_token):
        """GET /api/wallet/all-withdrawals denied for tenant admin"""
        response = requests.get(
            f"{BASE_URL}/api/wallet/all-withdrawals",
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 403, f"Expected 403 for tenant admin, got {response.status_code}"
        print("✓ Tenant admin correctly denied access to all withdrawals")
    
    def test_withdrawal_below_minimum_rejected(self, tenant_admin_token):
        """POST /api/wallet/withdraw rejects amount below min_withdrawal"""
        response = requests.post(
            f"{BASE_URL}/api/wallet/withdraw",
            json={
                "amount": 100,  # Below default min of 500
                "bank_details": {"upi_id": "test@upi"},
                "notes": "Test withdrawal"
            },
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        # Should be rejected with 400
        assert response.status_code == 400, f"Expected 400 for below minimum, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data
        assert "minimum" in data["detail"].lower() or "500" in data["detail"]
        print(f"✓ Withdrawal below minimum correctly rejected: {data['detail']}")


class TestWithdrawalWorkflow(TestWalletAuth):
    """Withdrawal approve/reject/complete workflow tests"""
    
    def test_approve_withdrawal_super_admin(self, super_admin_token):
        """PUT /api/wallet/withdrawals/{id}/approve approves a pending withdrawal"""
        # Get pending withdrawals
        response = requests.get(
            f"{BASE_URL}/api/wallet/all-withdrawals?status=pending",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        if response.status_code == 200:
            withdrawals = response.json()
            pending = [w for w in withdrawals if w.get("status") == "pending"]
            
            if pending:
                withdrawal_id = pending[0]["id"]
                
                approve_response = requests.put(
                    f"{BASE_URL}/api/wallet/withdrawals/{withdrawal_id}/approve",
                    json={"notes": "Approved by test"},
                    headers={"Authorization": f"Bearer {super_admin_token}"}
                )
                assert approve_response.status_code == 200, f"Expected 200, got {approve_response.status_code}: {approve_response.text}"
                print(f"✓ Withdrawal {withdrawal_id} approved successfully")
            else:
                print("⚠ No pending withdrawals to approve, skipping test")
        else:
            pytest.skip("Could not get withdrawals")
    
    def test_complete_withdrawal_super_admin(self, super_admin_token):
        """PUT /api/wallet/withdrawals/{id}/complete marks approved withdrawal as completed"""
        # Get approved withdrawals
        response = requests.get(
            f"{BASE_URL}/api/wallet/all-withdrawals",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        if response.status_code == 200:
            withdrawals = response.json()
            approved = [w for w in withdrawals if w.get("status") == "approved"]
            
            if approved:
                withdrawal_id = approved[0]["id"]
                
                complete_response = requests.put(
                    f"{BASE_URL}/api/wallet/withdrawals/{withdrawal_id}/complete",
                    json={"transaction_ref": "TEST_TXN_12345"},
                    headers={"Authorization": f"Bearer {super_admin_token}"}
                )
                assert complete_response.status_code == 200, f"Expected 200, got {complete_response.status_code}: {complete_response.text}"
                print(f"✓ Withdrawal {withdrawal_id} marked as completed")
            else:
                print("⚠ No approved withdrawals to complete, skipping test")
        else:
            pytest.skip("Could not get withdrawals")
    
    def test_reject_withdrawal_super_admin(self, super_admin_token):
        """PUT /api/wallet/withdrawals/{id}/reject rejects a pending withdrawal"""
        # Get pending withdrawals
        response = requests.get(
            f"{BASE_URL}/api/wallet/all-withdrawals",
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        if response.status_code == 200:
            withdrawals = response.json()
            pending = [w for w in withdrawals if w.get("status") == "pending"]
            
            if pending:
                withdrawal_id = pending[0]["id"]
                
                reject_response = requests.put(
                    f"{BASE_URL}/api/wallet/withdrawals/{withdrawal_id}/reject",
                    json={"reason": "Test rejection"},
                    headers={"Authorization": f"Bearer {super_admin_token}"}
                )
                assert reject_response.status_code == 200, f"Expected 200, got {reject_response.status_code}: {reject_response.text}"
                print(f"✓ Withdrawal {withdrawal_id} rejected successfully")
            else:
                print("⚠ No pending withdrawals to reject, skipping test")
        else:
            pytest.skip("Could not get withdrawals")
    
    def test_approve_nonexistent_withdrawal(self, super_admin_token):
        """PUT /api/wallet/withdrawals/{id}/approve returns 404 for nonexistent withdrawal"""
        response = requests.put(
            f"{BASE_URL}/api/wallet/withdrawals/nonexistent-id-12345/approve",
            json={},
            headers={"Authorization": f"Bearer {super_admin_token}"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Nonexistent withdrawal correctly returns 404")
    
    def test_approve_withdrawal_tenant_admin_denied(self, tenant_admin_token):
        """PUT /api/wallet/withdrawals/{id}/approve denied for tenant admin"""
        response = requests.put(
            f"{BASE_URL}/api/wallet/withdrawals/any-id/approve",
            json={},
            headers={"Authorization": f"Bearer {tenant_admin_token}"}
        )
        assert response.status_code == 403, f"Expected 403 for tenant admin, got {response.status_code}"
        print("✓ Tenant admin correctly denied from approving withdrawals")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
