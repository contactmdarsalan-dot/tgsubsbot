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
        "success", "done", "approved", "Rs.", "rs"
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


def create_blurred_image(image_bytes: bytes, blur_radius: int = 10, content_type: str = "photo") -> bytes:
    """Create a blurred version of an image for paid post preview."""
    from PIL import ImageFilter

    try:
        image = Image.open(BytesIO(image_bytes))
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')

        if content_type == "photo":
            actual_blur = blur_radius if blur_radius > 15 else 25
            overlay_alpha = 80
        else:
            actual_blur = blur_radius if blur_radius < 15 else 10
            overlay_alpha = 30

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
    """Use GPT-4o Vision to analyze payment screenshot."""
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
            system_message="""You are an expert payment screenshot analyzer. Your job is to:
1. FIRST determine if this is actually a payment screenshot or something else (selfie, random photo, meme, etc.)
2. Extract payment details (amount, UPI ID, transaction ID, date/time, payment app, status)
3. Detect if the screenshot is fake/edited (look for: inconsistent fonts, pixel artifacts, wrong shadows, misaligned elements, suspicious timestamps)
4. Verify if payment status shows "Success", "Completed", or "Paid"
5. Match amount and UPI ID if provided

RESPOND ONLY IN THIS JSON FORMAT:
{
    "is_payment_screenshot": true/false,
    "is_valid_payment": true/false,
    "confidence_score": 0-100,
    "extracted_data": {
        "amount": "extracted amount as number or null",
        "upi_id": "extracted UPI ID or null",
        "transaction_id": "extracted transaction ID or null",
        "payment_app": "GPay/PhonePe/Paytm/etc or null",
        "status": "Success/Completed/Failed/Pending or null",
        "timestamp": "extracted date/time or null"
    },
    "fake_indicators": ["list of suspicious elements found"],
    "amount_matches": true/false/null,
    "upi_id_matches": true/false/null,
    "auto_approve_recommended": true/false,
    "reason": "brief explanation"
}

IMPORTANT: If this is NOT a payment screenshot (selfie, random image, meme, etc.), set is_payment_screenshot to false."""
        ).with_model("openai", "gpt-4o")

        prompt = "Analyze this payment screenshot and extract all details. Check if it's a genuine payment confirmation."
        if expected_amount:
            prompt += f"\n\nExpected payment amount: Rs.{expected_amount}"
        if expected_upi_id:
            prompt += f"\nExpected UPI ID: {expected_upi_id}"

        image_content = ImageContent(image_base64=image_base64)
        user_message = UserMessage(
            text=prompt,
            file_contents=[image_content]
        )

        response = await chat.send_message(user_message)
        logger.info(f"AI Payment Analysis Response: {response[:500]}")

        try:
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()

            result = json.loads(json_str)
            result["ai_enabled"] = True
            result["raw_response"] = response[:500]

            if result.get("confidence_score", 0) >= 85 and result.get("is_valid_payment", False):
                if not result.get("fake_indicators") or len(result.get("fake_indicators", [])) == 0:
                    result["auto_approve_recommended"] = True
                else:
                    result["auto_approve_recommended"] = False

            return result

        except json.JSONDecodeError as je:
            logger.error(f"Failed to parse AI response as JSON: {je}")
            return {
                "ai_enabled": True,
                "is_valid_payment": False,
                "confidence_score": 0,
                "auto_approve_recommended": False,
                "error": "Failed to parse AI response",
                "raw_response": response[:500]
            }

    except Exception as e:
        logger.error(f"AI Payment Analysis Error: {e}")
        return {
            "ai_enabled": True,
            "is_valid_payment": False,
            "confidence_score": 0,
            "auto_approve_recommended": False,
            "error": str(e)
        }
