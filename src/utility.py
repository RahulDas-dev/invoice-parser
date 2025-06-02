import io
import os
from pathlib import Path
import re
from PIL import Image


def get_secret_keys() -> dict:
    return {
        "aws_access_key_id": os.getenv("AWS_ACCESS_KEY"),
        "aws_secret_access_key": os.getenv("AWS_SECRET_KEY"),
        "region_name": os.getenv("REGION_NAME"),
    }


def image_to_byte_string(image_path: str | Path) -> tuple[bytes, str]:
    image = Image.open(image_path)
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format="PNG")  # or 'JPEG', etc.
    img_byte_arr = img_byte_arr.getvalue()
    return img_byte_arr, image.get_format_mimetype() or "image/png"


def extract_json_from_text(text: str) -> str | None:
    """
    Extract JSON-like content from a string.

    Args:
        text: The input string containing JSON-like content
    Returns:
        Extracted JSON string or an empty string if no valid JSON is found
    """
    # Regular expression to match JSON-like content
    json_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    match = re.search(json_pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else None


DEFAULT_INVOICE_METADATA = {
    "invoice_number": "NOT_AVAILABLE",
    "line_item_start_number": "NOT_AVAILABLE",
    "line_item_end_number": "NOT_AVAILABLE",
    "line_items_present": False,
    "total_amount": "NOT_AVAILABLE",
    "seller_details_present": False,
    "buyer_details_present": False,
}


def extract_invoice_metadata(text: str) -> dict[str, str | bool]:
    """
    Extracts the page number from the page content.

    Args:
        page_content: The content of the invoice page

    Returns:
        A string indicating the page number
    """

    field_patterns = {
        "invoice_number": r'"invoice_number"\s*:\s*"([^"]+)"',
        "line_item_start_number": r'"line_item_start_number"\s*:\s*([\d]+)',
        "line_item_end_number": r'"line_item_end_number"\s*:\s*([\d]+)',
        "line_items_present": r'"line_items_present"\s*:\s*(true|false|True|False)',
        "total_amount": r'"total_amount"\s*:\s*"([\d,.]+)(?:[^"]*)"',
        "seller_details_present": r'"seller_details_present"\s*:\s*(true|false|True|False)',
        "buyer_details_present": r'"buyer_details_present"\s*:\s*(true|false|True|False)',
    }
    extracted = DEFAULT_INVOICE_METADATA.copy()
    text_lower = text.lower()
    for key, pat in field_patterns.items():
        match = re.search(pat, text_lower)
        if match:
            val = match.group(1)
            if key in [
                "line_items_present",
                "seller_details_present",
                "buyer_details_present",
            ]:
                extracted[key] = val.lower() == "true"
            else:
                extracted[key] = val
    return extracted
