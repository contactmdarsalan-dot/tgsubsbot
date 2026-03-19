import requests
import sys
import json
from datetime import datetime

class TelegramBotAPITester:
    def __init__(self, base_url="https://telegram-sub-admin.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.created_resources = {
            'plans': [],
            'subscribers': [],
            'payments': []
        }

    def log_result(self, test_name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
        
        result = {
            'test': test_name,
            'success': success,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}")
        if details:
            print(f"    Details: {details}")

    def run_test(self, name, method, endpoint, expected_status, data=None, auth_required=True):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if auth_required and self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=10)

            success = response.status_code == expected_status
            
            if success:
                try:
                    response_data = response.json()
                    self.log_result(name, True, f"Status: {response.status_code}")
                    return True, response_data
                except:
                    self.log_result(name, True, f"Status: {response.status_code} (No JSON)")
                    return True, {}
            else:
                try:
                    error_data = response.json()
                    self.log_result(name, False, f"Expected {expected_status}, got {response.status_code}: {error_data}")
                except:
                    self.log_result(name, False, f"Expected {expected_status}, got {response.status_code}")
                return False, {}

        except Exception as e:
            self.log_result(name, False, f"Exception: {str(e)}")
            return False, {}

    def test_auth_flow(self):
        """Test authentication endpoints"""
        print("\n🔐 Testing Authentication Flow...")
        
        # Test user registration
        test_user = {
            "email": f"test_{datetime.now().strftime('%H%M%S')}@example.com",
            "password": "TestPass123!",
            "name": "Test User"
        }
        
        success, response = self.run_test(
            "User Registration",
            "POST",
            "auth/register",
            200,
            data=test_user,
            auth_required=False
        )
        
        if success and 'token' in response:
            self.token = response['token']
            self.log_result("Token Retrieved", True, "Authentication token obtained")
        else:
            self.log_result("Token Retrieved", False, "No token in registration response")
            return False

        # Test login with same credentials
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"]
        }
        
        success, response = self.run_test(
            "User Login",
            "POST",
            "auth/login",
            200,
            data=login_data,
            auth_required=False
        )

        # Test get current user
        self.run_test(
            "Get Current User",
            "GET",
            "auth/me",
            200
        )

        return True

    def test_plans_crud(self):
        """Test subscription plans CRUD operations"""
        print("\n📋 Testing Plans CRUD...")
        
        # Create a plan
        plan_data = {
            "name": "Test Premium Plan",
            "price": 299.0,
            "duration_days": 30,
            "features": ["Premium access", "24/7 support", "Advanced features"],
            "is_active": True
        }
        
        success, response = self.run_test(
            "Create Plan",
            "POST",
            "plans",
            200,
            data=plan_data
        )
        
        plan_id = None
        if success and 'id' in response:
            plan_id = response['id']
            self.created_resources['plans'].append(plan_id)
            self.log_result("Plan ID Retrieved", True, f"Plan ID: {plan_id}")
        
        # Get all plans
        self.run_test(
            "Get All Plans",
            "GET",
            "plans",
            200
        )
        
        # Get active plans (public endpoint)
        success, response = self.run_test(
            "Get Active Plans",
            "GET",
            "plans/active",
            200,
            auth_required=False
        )
        
        # Update plan if we have an ID
        if plan_id:
            updated_plan = {
                "name": "Updated Premium Plan",
                "price": 399.0,
                "duration_days": 30,
                "features": ["Updated premium access", "24/7 support"],
                "is_active": True
            }
            
            self.run_test(
                "Update Plan",
                "PUT",
                f"plans/{plan_id}",
                200,
                data=updated_plan
            )
        
        return plan_id

    def test_subscribers_management(self, plan_id):
        """Test subscriber management"""
        print("\n👥 Testing Subscribers Management...")
        
        if not plan_id:
            self.log_result("Subscribers Test Skipped", False, "No plan ID available")
            return None
        
        # Create a subscriber
        subscriber_data = {
            "telegram_user_id": "123456789",
            "telegram_username": "testuser",
            "plan_id": plan_id,
            "payment_method": "manual"
        }
        
        success, response = self.run_test(
            "Create Subscriber",
            "POST",
            "subscribers",
            200,
            data=subscriber_data
        )
        
        subscriber_id = None
        if success and 'id' in response:
            subscriber_id = response['id']
            self.created_resources['subscribers'].append(subscriber_id)
        
        # Get all subscribers
        self.run_test(
            "Get All Subscribers",
            "GET",
            "subscribers",
            200
        )
        
        # Get subscribers by status
        self.run_test(
            "Get Active Subscribers",
            "GET",
            "subscribers?status=active",
            200
        )
        
        # Test renewal if we have subscriber ID
        if subscriber_id:
            self.run_test(
                "Renew Subscriber",
                "PUT",
                f"subscribers/{subscriber_id}/renew?plan_id={plan_id}",
                200
            )
        
        return subscriber_id

    def test_payments_system(self, plan_id):
        """Test payment system"""
        print("\n💳 Testing Payments System...")
        
        if not plan_id:
            self.log_result("Payments Test Skipped", False, "No plan ID available")
            return
        
        # Create manual payment
        payment_data = {
            "telegram_user_id": "987654321",
            "plan_id": plan_id,
            "amount": 299.0,
            "payment_method": "manual"
        }
        
        success, response = self.run_test(
            "Create Manual Payment",
            "POST",
            "payments/manual",
            200,
            data=payment_data
        )
        
        payment_id = None
        if success and 'payment_id' in response:
            payment_id = response['payment_id']
            self.created_resources['payments'].append(payment_id)
        
        # Get all payments
        self.run_test(
            "Get All Payments",
            "GET",
            "payments",
            200
        )
        
        # Get pending payments
        self.run_test(
            "Get Pending Payments",
            "GET",
            "payments?status=pending",
            200
        )
        
        # Verify manual payment if we have payment ID
        if payment_id:
            self.run_test(
                "Verify Manual Payment",
                "PUT",
                f"payments/{payment_id}/verify-manual",
                200
            )

    def test_settings_management(self):
        """Test settings management"""
        print("\n⚙️ Testing Settings Management...")
        
        # Get current settings
        success, response = self.run_test(
            "Get Settings",
            "GET",
            "settings",
            200
        )
        
        # Update settings
        settings_data = {
            "id": "bot_settings",
            "telegram_bot_token": "test_token_123",
            "telegram_channel_id": "-1001234567890",
            "website_link": "https://example.com",
            "qr_code_url": "https://example.com/qr.png",
            "reminder_days_before": 3,
            "grace_period_days": 2,
            "followup_enabled": True,
            "followup_message": "Check out our services!"
        }
        
        self.run_test(
            "Update Settings",
            "PUT",
            "settings",
            200,
            data=settings_data
        )

    def test_analytics_dashboard(self):
        """Test analytics endpoint"""
        print("\n📊 Testing Analytics Dashboard...")
        
        self.run_test(
            "Get Analytics",
            "GET",
            "analytics",
            200
        )

    def test_message_templates(self):
        """Test message templates CRUD"""
        print("\n📝 Testing Message Templates...")
        
        # Create template
        template_data = {
            "type": "welcome",
            "message": "Welcome to our premium service! 🎉",
            "is_active": True
        }
        
        success, response = self.run_test(
            "Create Template",
            "POST",
            "templates",
            200,
            data=template_data
        )
        
        template_id = None
        if success and 'id' in response:
            template_id = response['id']
        
        # Get all templates
        self.run_test(
            "Get All Templates",
            "GET",
            "templates",
            200
        )
        
        # Update template if we have ID
        if template_id:
            updated_template = {
                "type": "welcome",
                "message": "Updated welcome message! 🚀",
                "is_active": True
            }
            
            self.run_test(
                "Update Template",
                "PUT",
                f"templates/{template_id}",
                200,
                data=updated_template
            )

    def cleanup_resources(self):
        """Clean up created test resources"""
        print("\n🧹 Cleaning up test resources...")
        
        # Delete subscribers
        for subscriber_id in self.created_resources['subscribers']:
            self.run_test(
                f"Delete Subscriber {subscriber_id}",
                "DELETE",
                f"subscribers/{subscriber_id}",
                200
            )
        
        # Delete plans
        for plan_id in self.created_resources['plans']:
            self.run_test(
                f"Delete Plan {plan_id}",
                "DELETE",
                f"plans/{plan_id}",
                200
            )

    def run_all_tests(self):
        """Run complete test suite"""
        print("🚀 Starting Telegram Subscription Bot API Tests")
        print(f"Testing against: {self.base_url}")
        print("=" * 60)
        
        # Test authentication first
        if not self.test_auth_flow():
            print("❌ Authentication failed, stopping tests")
            return False
        
        # Test all endpoints
        plan_id = self.test_plans_crud()
        subscriber_id = self.test_subscribers_management(plan_id)
        self.test_payments_system(plan_id)
        self.test_settings_management()
        self.test_analytics_dashboard()
        self.test_message_templates()
        
        # Cleanup
        self.cleanup_resources()
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        print(f"Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("🎉 Backend API tests mostly successful!")
            return True
        else:
            print("⚠️ Multiple backend issues detected")
            return False

def main():
    tester = TelegramBotAPITester()
    success = tester.run_all_tests()
    
    # Save detailed results
    with open('/app/backend_test_results.json', 'w') as f:
        json.dump({
            'summary': {
                'total_tests': tester.tests_run,
                'passed_tests': tester.tests_passed,
                'success_rate': (tester.tests_passed / tester.tests_run * 100) if tester.tests_run > 0 else 0,
                'timestamp': datetime.now().isoformat()
            },
            'detailed_results': tester.test_results
        }, f, indent=2)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())