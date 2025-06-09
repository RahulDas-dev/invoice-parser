from collections.abc import Mapping
import logging
import re
from typing import Any
from pydantic import BaseModel, Field
from output_format import Invoice


logger = logging.getLogger(__name__)


class PageDetails(BaseModel):
    page_index: int
    image_path: str
    image_size: tuple[int, int] = Field(default_factory=lambda: (0, 0))
    text_content: str | None = None
    metadata: Mapping[str, Any] = Field(default_factory=dict)


class TokenCount(BaseModel):
    model_name: str
    page_no: str
    request_tokens: int
    response_tokens: int


class PageGroup(BaseModel):
    group_name: str = Field(..., description="Use The Invoice Number as Group Name")
    page_nos: list[str] = Field(
        ...,
        description="List of page indices that belong to this invioice group , e.g., [P2, P3, P4]",
        default_factory=list,
    )
    details: Mapping[str, Any] = Field(default_factory=dict)

    @property
    def pages(self) -> list[int]:
        return [int(re.search(r"P(\d+)", page).group(1)) for page in self.page_nos]

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
        ...,
        description="List of page groups with their names and associated page indices",
        default_factory=list,
    )


class WorkflowState(BaseModel):
    pdf_name: str
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
        pages_content = [
            p_data.text_content
            for p_data in self.page_details
            if p_data.page_index in group.pages
        ]
        if group.is_multi_page:
            page_group_content = "\n".join(pages_content)
        else:
            page_group_content = pages_content[0] if pages_content else ""
        return page_group_content
