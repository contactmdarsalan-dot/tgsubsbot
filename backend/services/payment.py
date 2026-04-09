"""Payment analysis - OCR detection, AI analysis, image blur"""
import base64
import uuid
from io import BytesIO
from PIL import Image
import pytesseract
from config import logger, EMERGENT_LLM_KEY


def detect_payment_screenshot(image_bytes: bytes) -> dict:
    """FAST OCR to detect if image is a valid payment screenshot."""
    from PIL import ImageOps

    payment_keywords = [
        "gpay", "google pay", "phonepe", "paytm", "bhim", "amazon pay",
        "upi", "paid", "payment", "successful", "completed", "transaction",
        "success", "done", "approved", "Rs.", "rs", "credited", "debited",
        "transferred", "sent", "received", "bank", "neft", "imps", "rtgs"
    ]

    try:
        image = Image.open(BytesIO(image_bytes))
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')

        extracted_text = ""

        gray = image.convert('L')
        try:
            text1 = pytesseract.image_to_string(gray, lang='eng', config='--psm 6 --oem 1')
            extracted_text += " " + text1
        except Exception:
            pass

        try:
            inv_gray = ImageOps.invert(gray)
            text2 = pytesseract.image_to_string(inv_gray, lang='eng', config='--psm 6 --oem 1')
            extracted_text += " " + text2
        except Exception:
            pass

        text_lower = extracted_text.lower()
        found_keywords = [k for k in payment_keywords if k in text_lower]
        is_valid = len(found_keywords) >= 1 or "success" in text_lower or "paid" in text_lower

        logger.info(f"Fast OCR: found {len(found_keywords)} keywords, valid={is_valid}")

        return {
            "is_valid": is_valid,
            "found_keywords": found_keywords,
            "extracted_text_preview": text_lower[:200]
        }

    except Exception as e:
        logger.error(f"OCR error: {e}")
        return {"is_valid": False, "error": str(e), "found_keywords": []}


def create_blurred_image(image_bytes: bytes, blur_radius: int = 25, content_type: str = "photo") -> bytes:
    """Create a blurred version of an image for paid post preview.
    blur_radius: 1-100, higher = more blur. Default 25 for photos, 10 for videos.
    """
    from PIL import ImageFilter

    try:
        image = Image.open(BytesIO(image_bytes))
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')

        # Use the provided blur_radius directly (1-100 scale)
        actual_blur = max(1, min(blur_radius, 100))
        
        if content_type == "video" and blur_radius <= 10:
            actual_blur = 10
            overlay_alpha = 30
        else:
            overlay_alpha = min(80, int(actual_blur * 1.5))

        blurred = image.filter(ImageFilter.GaussianBlur(radius=actual_blur))
        overlay = Image.new('RGBA', blurred.size, (0, 0, 0, overlay_alpha))
        blurred = blurred.convert('RGBA')
        blurred = Image.alpha_composite(blurred, overlay)
        blurred = blurred.convert('RGB')

        output = BytesIO()
        blurred.save(output, format='JPEG', quality=85)
        logger.info(f"Blurred image created ({content_type}): blur={actual_blur}, size={len(output.getvalue())} bytes")
        return output.getvalue()

    except Exception as e:
        logger.error(f"Error creating blurred image: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


async def analyze_payment_screenshot_with_ai(image_bytes: bytes, expected_amount: float = None, expected_upi_id: str = None) -> dict:
    """Use GPT-5.2 Vision to analyze payment screenshot.
    
    LOGIC: Only check if image is a genuine transaction/payment screenshot.
    If yes → auto approve (amount/UPI/time mismatch doesn't matter).
    If no (selfie, meme, random image) → reject.
    """
    if not EMERGENT_LLM_KEY:
        logger.warning("EMERGENT_LLM_KEY not configured, skipping AI analysis")
        return {"ai_enabled": False, "error": "AI not configured"}

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
        import json

        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"payment-analysis-{uuid.uuid4()}",
            system_message="""You are a payment screenshot detector. Your ONLY job is to determine if the image is a REAL payment/transaction screenshot or not.

APPROVE if the image shows ANY of these:
- UPI payment confirmation (GPay, PhonePe, Paytm, BHIM, Amazon Pay, etc.)
- Bank transfer confirmation (NEFT, IMPS, RTGS)
- Any payment success/completed screen
- Any transaction receipt or confirmation
- Any money transfer screenshot
- Even if amount doesn't match, UPI ID doesn't match, or time is old - STILL APPROVE if it's a real transaction screenshot

REJECT ONLY if the image is:
- A selfie or face photo
- A random photo (nature, food, meme, etc.)
- A blank or corrupted image
- Clearly NOT a payment/transaction screenshot
- A fake/obviously photoshopped screenshot with glaring artifacts

RESPOND ONLY IN THIS EXACT JSON FORMAT:
{
    "is_payment_screenshot": true/false,
    "is_valid_payment": true/false,
    "confidence_score": 0-100,
    "extracted_data": {
        "amount": "extracted amount or null",
        "upi_id": "extracted UPI ID or null",
        "transaction_id": "extracted txn ID or null",
        "payment_app": "GPay/PhonePe/Paytm/etc or null",
        "status": "Success/Completed/Failed/Pending or null",
        "timestamp": "extracted date/time or null"
    },
    "auto_approve_recommended": true/false,
    "reason": "brief explanation"
}

IMPORTANT RULES:
1. If is_payment_screenshot is true → auto_approve_recommended MUST be true
2. Amount mismatch does NOT matter - still approve
3. UPI ID mismatch does NOT matter - still approve  
4. Old timestamp does NOT matter - still approve
5. Only reject if it's genuinely NOT a transaction screenshot"""
        ).with_model("openai", "gpt-5.2")

        prompt = "Is this a real payment/transaction screenshot? Analyze and respond in the required JSON format."

        image_content = ImageContent(image_base64=image_base64)
        user_message = UserMessage(
            text=prompt,
            file_contents=[image_content]
        )

        response = await chat.send_message(user_message)
        logger.info(f"AI Payment Analysis (GPT-5.2): {response[:500]}")

        try:
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()

            result = json.loads(json_str)
            result["ai_enabled"] = True
            result["raw_response"] = response[:500]
            result["model"] = "gpt-5.2"

            # Auto approve logic: if it's a payment screenshot → approve
            if result.get("is_payment_screenshot", False):
                result["auto_approve_recommended"] = True
                result["is_valid_payment"] = True
                # Boost confidence for payment screenshots
                if result.get("confidence_score", 0) < 85:
                    result["confidence_score"] = 90

            return result

        except json.JSONDecodeError as je:
            logger.error(f"Failed to parse AI response as JSON: {je}")
            return {
                "ai_enabled": True,
                "is_valid_payment": False,
                "confidence_score": 0,
                "auto_approve_recommended": False,
                "error": "Failed to parse AI response",
                "raw_response": response[:500],
                "model": "gpt-5.2"
            }

    except Exception as e:
        logger.error(f"AI Payment Analysis Error: {e}")
        return {
            "ai_enabled": True,
            "is_valid_payment": False,
            "confidence_score": 0,
            "auto_approve_recommended": False,
            "error": str(e),
            "model": "gpt-5.2"
        }
