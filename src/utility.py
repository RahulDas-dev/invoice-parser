import asyncio
import io
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import AsyncGenerator

from PIL import Image
from pydantic_ai.models import Model


async def async_range(count: int) -> AsyncGenerator[int, None]:
    for i in range(count):
        yield i
        await asyncio.sleep(0.0)


def get_aws_keys() -> dict:
    return {
        "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
        "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
        "region_name": os.getenv("AWS_REGION_NAME"),
    }


def extract_page_no(file: Path, image_ext: str = "png") -> tuple[Path, int]:
    match = re.search(rf"Page_(\d+)\.{image_ext}", file.name)
    return file, int(match.group(1) if match else 10e5)


async def sorted_images(image_dir: str | Path, image_ext: str = "png") -> AsyncGenerator[tuple[Path, int], None]:
    """Yields image files and their page numbers, sorted by page number."""
    image_files = list(Path(image_dir).rglob(f"*.{image_ext}"))

    for img_path, page_no in sorted(map(extract_page_no, image_files), key=lambda x: x[1]):
        await asyncio.sleep(0)  # Small sleep to make this a true async generator
        yield img_path, page_no


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


def replace_json_from_text(text: str) -> str:
    """
    Replace JSON-like content in a string with a placeholder.

    Args:
        text: The input string containing JSON-like content
    Returns:
        The modified string with JSON-like content replaced by a placeholder
    """
    json_pattern = r"```(?:json)?\s*\{.*?\}\s*```"
    pattern1 = r"^\s*#+\s*structured text output\s*$\n?"
    pattern2 = r"^\s*#+\s*json output\s*$\n?"
    # json_pattern = r"(?i)```json\s*{.*?}\s*```"
    cleaned_text = re.sub(json_pattern, "", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned_text = re.sub(pattern1, "", cleaned_text, flags=re.MULTILINE | re.IGNORECASE)
    cleaned_text = re.sub(pattern2, "", cleaned_text, flags=re.MULTILINE | re.IGNORECASE)
    return cleaned_text.strip()


DEFAULT_INVOICE_METADATA = {
    "invoice_number": "NOT_AVAILABLE",
    "line_item_start_number": "NOT_AVAILABLE",
    "line_item_end_number": "NOT_AVAILABLE",
    "line_items_present": False,
    "total_amount": "NOT_AVAILABLE",
    "seller_details_present": False,
    "buyer_details_present": False,
}


def extract_invoice_metadata(text: str) -> Mapping[str, str | bool]:
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
        "total_invoice_amount": r'"total_invoice_amount"\s*:\s*(?:")?([^",}]*)(?:")?',
        "seller_details_present": r'"seller_details_present"\s*:\s*(true|false|True|False)',
        "buyer_details_present": r'"buyer_details_present"\s*:\s*(true|false|True|False)',
        "invoice_date_present": r'"invoice_date_present"\s*:\s*(true|false|True|False)',
        "invoice_due_date_present": r'"invoice_due_date_present"\s*:\s*(true|false|True|False)',
        "total_tax_details_present": r'"total_tax_details_present"\s*:\s*(true|false|True|False)',
        "total_charges_present": r'"total_charges_present"\s*:\s*(true|false|True|False)',
        "total_discount_present": r'"total_discount_present"\s*:\s*(true|false|True|False)',
        "amount_paid_present": r'"amount_paid_present"\s*:\s*(true|false|True|False)',
        "amount_due_present": r'"amount_due_present"\s*:\s*(true|false|True|False)',
    }
    metadata = DEFAULT_INVOICE_METADATA.copy()
    text_lower = text.lower()
    for key, pat in field_patterns.items():
        match = re.search(pat, text_lower)
        if match:
            val = match.group(1)
            if key in [
                "line_items_present",
                "seller_details_present",
                "buyer_details_present",
                "invoice_date_present",
                "invoice_due_date_present",
                "total_tax_details_present",
                "total_charges_present",
                "total_discount_present",
                "amount_paid_present",
                "amount_due_present",
            ]:
                metadata[key] = val.lower() == "true"
            else:
                metadata[key] = val
    return metadata


def model_factory(model_name: str, provider: str = "openai") -> Model:
    """
    Factory function to create a model instance based on the model name and provider.

    Args:
        model_name: The name of the model to instantiate.
        provider: The provider of the model (default is "openai").

    Returns:
        An instance of the specified model.
    """
    if provider == "aws_bedrock":
        from pydantic_ai.models.bedrock import BedrockConverseModel
        from pydantic_ai.providers.bedrock import BedrockProvider

        return BedrockConverseModel(
            model_name=model_name,
            provider=BedrockProvider(**get_aws_keys()),
        )
    if provider == "openai":
        from pydantic_ai.models.openai import OpenAIModel

        return OpenAIModel(model_name=model_name)
    if provider == "azure":
        from openai import AsyncAzureOpenAI
        from pydantic_ai.models.openai import OpenAIModel
        from pydantic_ai.providers.azure import AzureProvider

        model_name_ = model_name or "finaclegpt4.1"
        if model_name_ not in ["finaclegpt4.1", "finaclegpt4o16k"]:
            raise ValueError("Invalid model name for Azure")

        return OpenAIModel(
            model_name_,
            provider=AzureProvider(
                openai_client=AsyncAzureOpenAI(
                    azure_endpoint=os.environ.get("AZURE_API_BASE", ""),
                    azure_deployment=model_name_,
                    api_version=os.environ.get("AZURE_API_VERSION"),
                    api_key=os.environ.get("AZURE_API_KEY"),
                )
            ),
        )
    raise ValueError(f"Unsupported provider: {provider}")
