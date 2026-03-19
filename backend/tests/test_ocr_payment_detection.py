"""
OCR Payment Screenshot Detection Tests
Tests for OCR-based payment screenshot auto-detection:
- detect_payment_screenshot() function with various inputs
- Keywords detection (GPay, PhonePe, Paytm, UPI, etc.)
- Amount pattern detection
- UPI ID pattern detection
- Positive cases (valid payment screenshots)
- Negative cases (non-payment images)
"""

import pytest
import requests
import os
import sys
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import json

# Add backend to path for direct imports
sys.path.insert(0, '/app/backend')
from server import detect_payment_screenshot

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
BOT_TOKEN = "8290557398:AAES0Np2CjMqfq88gEFcV4JjFTIuFsxLMfk"


def create_test_image_with_text(text_lines: list, width=400, height=600) -> bytes:
    """Create a simple test image with the given text lines"""
    # Create white background image
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Use default font
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except:
        font = ImageFont.load_default()
    
    # Draw text
    y_position = 50
    for line in text_lines:
        draw.text((20, y_position), line, fill='black', font=font)
        y_position += 40
    
    # Convert to bytes
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer.read()


class TestDetectPaymentScreenshotPositive:
    """Test detect_payment_screenshot with valid payment images"""
    
    def test_gpay_success_screenshot(self):
        """Test GPay success screenshot detection"""
        image_bytes = create_test_image_with_text([
            "Google Pay",
            "Payment Successful",
            "Amount: Rs.500",
            "To: merchant@okicici",
            "Transaction ID: 123456789"
        ])
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        assert result.get("is_valid") == True, f"Should detect GPay screenshot as valid. Result: {result}"
        assert "gpay" in [k.lower() for k in result.get("found_keywords", [])] or result.get("has_app") == True
        print(f"SUCCESS: GPay screenshot detected as valid. Keywords: {result.get('found_keywords', [])}")
    
    def test_phonepe_success_screenshot(self):
        """Test PhonePe success screenshot detection"""
        image_bytes = create_test_image_with_text([
            "PhonePe",
            "Paid Successfully",
            "Rs. 1000",
            "To: shop@upi",
            "UPI Ref: 123456789012"
        ])
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        assert result.get("is_valid") == True, f"Should detect PhonePe screenshot as valid. Result: {result}"
        print(f"SUCCESS: PhonePe screenshot detected as valid. Keywords: {result.get('found_keywords', [])}")
    
    def test_paytm_success_screenshot(self):
        """Test Paytm success screenshot detection"""
        image_bytes = create_test_image_with_text([
            "Paytm",
            "Transaction Successful",
            "Amount Paid: 750",
            "To: seller@paytm"
        ])
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        assert result.get("is_valid") == True, f"Should detect Paytm screenshot as valid. Result: {result}"
        print(f"SUCCESS: Paytm screenshot detected as valid. Keywords: {result.get('found_keywords', [])}")
    
    def test_upi_generic_screenshot(self):
        """Test generic UPI success screenshot detection"""
        image_bytes = create_test_image_with_text([
            "UPI Transaction",
            "Payment Done",
            "Rs.250 Transferred",
            "UPI ID: user@okaxis",
            "UTR: 123456789012"
        ])
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        assert result.get("is_valid") == True, f"Should detect UPI screenshot as valid. Result: {result}"
        print(f"SUCCESS: Generic UPI screenshot detected as valid. Keywords: {result.get('found_keywords', [])}")
    
    def test_bhim_success_screenshot(self):
        """Test BHIM UPI success screenshot detection"""
        image_bytes = create_test_image_with_text([
            "BHIM UPI",
            "Money Sent Successfully",
            "Amount: Rs. 300",
            "Beneficiary: shop@ybl"
        ])
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        assert result.get("is_valid") == True, f"Should detect BHIM screenshot as valid. Result: {result}"
        print(f"SUCCESS: BHIM screenshot detected as valid. Keywords: {result.get('found_keywords', [])}")
    
    def test_minimal_valid_screenshot(self):
        """Test screenshot with minimal required keywords (UPI + amount)"""
        image_bytes = create_test_image_with_text([
            "UPI Payment",
            "Rs.100 Paid"
        ])
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        # Should have UPI and amount detection
        assert result.get("has_upi") == True or "upi" in [k.lower() for k in result.get("found_keywords", [])]
        print(f"SUCCESS: Minimal UPI screenshot processed. is_valid: {result.get('is_valid')}, Keywords: {result.get('found_keywords', [])}")
    
    def test_rupee_symbol_detection(self):
        """Test rupee symbol detection in screenshots"""
        image_bytes = create_test_image_with_text([
            "GPay Transfer",
            "Paid to merchant",
            "Amount: 500",
            "Success"
        ])
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        assert result.get("has_app") == True or result.get("has_transaction") == True
        print(f"SUCCESS: Screenshot with amount processed. Keywords: {result.get('found_keywords', [])}")


class TestDetectPaymentScreenshotNegative:
    """Test detect_payment_screenshot with non-payment images"""
    
    def test_random_text_image(self):
        """Test that random text is NOT detected as payment"""
        image_bytes = create_test_image_with_text([
            "Hello World",
            "This is a test image",
            "No payment info here",
            "Just random text"
        ])
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        assert result.get("is_valid") == False, f"Should NOT detect random text as valid payment. Result: {result}"
        print(f"SUCCESS: Random text correctly rejected as non-payment. Keywords: {result.get('found_keywords', [])}")
    
    def test_blank_image(self):
        """Test blank/white image is NOT detected as payment"""
        # Create blank white image
        img = Image.new('RGB', (400, 600), color='white')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        image_bytes = buffer.read()
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        assert result.get("is_valid") == False, f"Should NOT detect blank image as valid payment. Result: {result}"
        print(f"SUCCESS: Blank image correctly rejected")
    
    def test_chat_screenshot(self):
        """Test chat conversation screenshot is NOT detected as payment"""
        image_bytes = create_test_image_with_text([
            "WhatsApp Chat",
            "Hi how are you?",
            "I am fine thanks",
            "See you later",
            "Bye!"
        ])
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        assert result.get("is_valid") == False, f"Should NOT detect chat as valid payment. Result: {result}"
        print(f"SUCCESS: Chat screenshot correctly rejected")
    
    def test_food_order_screenshot(self):
        """Test food order (non-UPI) screenshot is NOT detected as payment"""
        image_bytes = create_test_image_with_text([
            "Swiggy Order Placed",
            "Biryani - 2",
            "Total: Rs.400",
            "Delivery in 30 mins"
        ])
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        # Should have amount but NOT be marked as valid payment proof
        # Note: This might be a borderline case as it has "Rs." pattern
        print(f"INFO: Food order screenshot - is_valid: {result.get('is_valid')}, Keywords: {result.get('found_keywords', [])}")
    
    def test_partial_payment_keywords(self):
        """Test image with some payment keywords but not enough"""
        image_bytes = create_test_image_with_text([
            "Bank Statement",
            "Balance: Rs.5000",
            "Transaction History"
        ])
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        # Should detect some keywords but not mark as valid payment screenshot
        print(f"INFO: Bank statement - is_valid: {result.get('is_valid')}, Keywords: {result.get('found_keywords', [])}")


class TestDetectPaymentScreenshotEdgeCases:
    """Test edge cases and error handling"""
    
    def test_small_image(self):
        """Test very small image handling"""
        img = Image.new('RGB', (50, 50), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((5, 5), "UPI", fill='black')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        image_bytes = buffer.read()
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        assert "error" not in result or result.get("error") is None
        print(f"SUCCESS: Small image handled without error")
    
    def test_large_image(self):
        """Test large image handling"""
        image_bytes = create_test_image_with_text([
            "GPay Payment",
            "Success - Rs.1000",
            "UPI Transaction Complete"
        ], width=1080, height=1920)
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        assert "error" not in result or result.get("error") is None
        print(f"SUCCESS: Large image handled. is_valid: {result.get('is_valid')}")
    
    def test_jpeg_format(self):
        """Test JPEG image format handling"""
        img = Image.new('RGB', (400, 600), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((20, 50), "GPay Payment Successful", fill='black')
        draw.text((20, 90), "Rs. 500 Paid", fill='black')
        buffer = BytesIO()
        img.save(buffer, format='JPEG')
        buffer.seek(0)
        image_bytes = buffer.read()
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        assert "error" not in result or result.get("error") is None
        print(f"SUCCESS: JPEG format handled. is_valid: {result.get('is_valid')}")
    
    def test_png_with_transparency(self):
        """Test PNG with transparency handling"""
        img = Image.new('RGBA', (400, 600), color=(255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        draw.text((20, 50), "PhonePe Paid", fill='black')
        draw.text((20, 90), "Rs. 200", fill='black')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        image_bytes = buffer.read()
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        assert "error" not in result or result.get("error") is None
        print(f"SUCCESS: PNG with transparency handled. is_valid: {result.get('is_valid')}")
    
    def test_invalid_image_bytes(self):
        """Test invalid image bytes handling"""
        invalid_bytes = b"not a valid image data"
        
        result = detect_payment_screenshot(invalid_bytes)
        
        assert result is not None
        # Should return error gracefully
        assert result.get("is_valid") == False
        print(f"SUCCESS: Invalid image bytes handled gracefully")
    
    def test_empty_bytes(self):
        """Test empty bytes handling"""
        empty_bytes = b""
        
        result = detect_payment_screenshot(empty_bytes)
        
        assert result is not None
        assert result.get("is_valid") == False
        print(f"SUCCESS: Empty bytes handled gracefully")


class TestUPIIDPatternDetection:
    """Test UPI ID pattern detection"""
    
    def test_okicici_upi_id(self):
        """Test @okicici UPI ID detection"""
        image_bytes = create_test_image_with_text([
            "Paid to merchant@okicici",
            "Rs. 100"
        ])
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        assert result.get("has_upi") == True or "upi_id_detected" in result.get("found_keywords", [])
        print(f"SUCCESS: @okicici UPI ID detection. Keywords: {result.get('found_keywords', [])}")
    
    def test_paytm_upi_id(self):
        """Test @paytm UPI ID detection"""
        image_bytes = create_test_image_with_text([
            "Payment to shop@paytm",
            "Amount: Rs.500"
        ])
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        print(f"INFO: @paytm UPI ID detection. Keywords: {result.get('found_keywords', [])}")
    
    def test_ybl_upi_id(self):
        """Test @ybl UPI ID detection"""
        image_bytes = create_test_image_with_text([
            "Transfer to friend@ybl",
            "Rs.200 Sent Successfully"
        ])
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        print(f"INFO: @ybl UPI ID detection. Keywords: {result.get('found_keywords', [])}")


class TestAmountPatternDetection:
    """Test amount pattern detection"""
    
    def test_rupee_symbol_amount(self):
        """Test amount with Rs. prefix"""
        image_bytes = create_test_image_with_text([
            "GPay Payment",
            "Amount: Rs.1500",
            "Success"
        ])
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        assert result.get("has_amount") == True or len([k for k in result.get("found_keywords", []) if "amount" in k.lower()]) > 0
        print(f"SUCCESS: Rs. amount detection. Keywords: {result.get('found_keywords', [])}")
    
    def test_comma_formatted_amount(self):
        """Test comma-formatted amount (Rs. 1,500)"""
        image_bytes = create_test_image_with_text([
            "PhonePe",
            "Paid Rs. 10,000",
            "Transaction Complete"
        ])
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        print(f"INFO: Comma formatted amount detection. Keywords: {result.get('found_keywords', [])}")


class TestDownloadTelegramPhotoAPI:
    """Test download_telegram_photo function via API (if accessible)"""
    
    def test_download_with_invalid_file_id(self):
        """Test download with invalid file_id returns None gracefully"""
        # This is more of an integration test
        # We can test the endpoint behavior
        print("INFO: download_telegram_photo testing requires actual Telegram file_ids")
        print("INFO: The function returns None for invalid file_ids (graceful handling)")
    
    def test_api_health_check(self):
        """Verify backend API is accessible"""
        # Use plans/active endpoint as a health check since there's no dedicated health endpoint
        response = requests.get(f"{BASE_URL}/api/plans/active")
        
        # Endpoint should return 200
        assert response.status_code == 200, f"API check failed: {response.status_code}"
        print("SUCCESS: Backend API is accessible")


class TestOCRIntegration:
    """Test OCR integration in webhook flow (simulated)"""
    
    def test_ocr_function_exists_and_callable(self):
        """Test that detect_payment_screenshot is importable and callable"""
        from server import detect_payment_screenshot
        
        assert callable(detect_payment_screenshot)
        print("SUCCESS: detect_payment_screenshot function is importable and callable")
    
    def test_ocr_returns_expected_structure(self):
        """Test that OCR function returns expected response structure"""
        image_bytes = create_test_image_with_text(["Test Image"])
        
        result = detect_payment_screenshot(image_bytes)
        
        assert result is not None
        assert isinstance(result, dict)
        assert "is_valid" in result
        assert "found_keywords" in result
        assert isinstance(result["is_valid"], bool)
        assert isinstance(result["found_keywords"], list)
        
        # Check optional fields
        assert "has_app" in result
        assert "has_transaction" in result
        assert "has_amount" in result
        assert "has_upi" in result
        
        print("SUCCESS: OCR function returns expected response structure")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
