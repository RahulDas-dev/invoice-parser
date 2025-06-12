import logging
import re
from collections.abc import Mapping
from string import Template
from typing import Any

from pydantic import BaseModel, Field

from src.output_format import Invoice

logger = logging.getLogger(__name__)

IMAGE_TO_TEXT_PAGE_TEMPLATE = Template("""
Page No $PAGE_NO

$PAGE_CONTENT
""")


class PageDetails(BaseModel):
    page_index: int
    image_path: str
    image_size: tuple[int, int] = Field(default_factory=lambda: (0, 0))
    text_content: str = Field(default="")
    metadata: Mapping[str, Any] = Field(default_factory=dict)
    invoice: Invoice | None = None

    @property
    def is_invoice_page(self) -> bool:
        """Check if the page contains invoice data."""
        if not self.text_content:
            return False
        patterns = r"\bNO_INVOICE_FOUND"
        match = re.search(patterns, self.text_content, re.IGNORECASE)
        return not match and len(self.metadata) > 0

    @property
    def invoice_number(self) -> str | None:
        """Extract the invoice number from the metadata."""
        invoice_number = self.metadata.get("invoice_number", "")
        return None if invoice_number.lower() in ["", "not_available"] else invoice_number

    def append_page_no(self) -> str:
        return IMAGE_TO_TEXT_PAGE_TEMPLATE.substitute(
            PAGE_NO=self.page_index,
            PAGE_CONTENT=self.text_content,
        )


class TokenCount(BaseModel):
    model_name: str
    page_no: str
    request_tokens: int = Field(default=0)
    response_tokens: int = Field(default=0)


class PageGroup(BaseModel):
    group_name: str = Field(..., description="Use The Invoice Number as Group Name")
    page_nos: list[str] = Field(
        description="List of page indices that belong to this invioice group , e.g., [P2, P3, P4]",
        default_factory=list,
    )
    details: Mapping[str, Any] = Field(default_factory=dict)

    @property
    def pages(self) -> list[int]:
        result = []
        for page in self.page_nos:
            match = re.search(r"P(\d+)", page)
            if match:
                result.append(int(match.group(1)))
        return result

    @property
    def size(self) -> int:
        return len(self.page_nos)

    @property
    def is_single_page(self) -> bool:
        return self.size == 1

    @property
    def is_multi_page(self) -> bool:
        return self.size > 1


class PageGroupInfo(BaseModel):
    group_info: list[PageGroup] = Field(
        description="List of page groups with their names and associated page indices",
        default_factory=list,
    )


class WorkflowState(BaseModel):
    pdf_name: str
    image_dir: str = ""
    page_details: list[PageDetails] = []
    page_group_info: list[PageGroup] = []
    token_count: list[TokenCount] = []
    final_output: list[Invoice] = []
    error: str | None = None

    @property
    def page_count(self) -> int:
        return len(self.page_details)

    def get_text_content_for_group(self, group_index: int) -> str:
        """Get the concatenated text content for a specific group."""
        group = self.page_group_info[group_index]
        pages_content = [p_data.text_content for p_data in self.page_details if p_data.page_index in group.pages]
        if group.is_multi_page:
            page_group_content = "\n".join(pages_content)
        else:
            page_group_content = pages_content[0] if pages_content else ""
        return page_group_content

    def valid_invoice_count(self) -> int:
        """Count the number of valid invoices in the final output."""
        valid_invoices = [
            p_data.invoice_number
            for p_data in self.page_details
            if p_data.is_invoice_page and p_data.invoice_number is not None
        ]
        logger.info(f"Valid Invoices: {valid_invoices}")
        return len(valid_invoices)

    def unique_invoice_count(self) -> int:
        """Get a set of unique invoice numbers from the page details."""
        valid_invoices = [
            p_data.invoice_number
            for p_data in self.page_details
            if p_data.is_invoice_page and p_data.invoice_number is not None
        ]
        return len(set(valid_invoices)) if valid_invoices else 0
