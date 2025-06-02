import asyncio
from dataclasses import dataclass
import logging
from pathlib import Path
import re
from pydantic import BaseModel, Field
from pydantic_graph import BaseNode, End, GraphRunContext
from src.config import InvoiceParserConfig, config
from src.output_format import Invoice
from src.pdf_2_image import Pdf2ImgConverter
from pydantic_ai import Agent, BinaryContent, ModelRetry
from pydantic_ai.models.bedrock import BedrockConverseModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.bedrock import BedrockProvider

from src.system_message import (
    PAGE_TEMPLATE,
    SYSTEM_MESSAGE_1,
    SYSTEM_MESSAGE_2,
    SYSTEM_MESSAGE_3,
    USER_MESSAGE_1,
    USER_MESSAGE_2,
)
from src.utility import (
    DEFAULT_INVOICE_METADATA,
    extract_invoice_metadata,
    extract_json_from_text,
    get_secret_keys,
    image_to_byte_string,
)

logger = logging.getLogger(__name__)


class PageMetadata(BaseModel):
    invoice_number: str | None = None
    line_item_start_number: int | None = None
    line_item_end_number: int | None = None
    line_items_present: bool = False
    total_amount: float | None = None
    seller_details_present: bool = False
    buyer_details_present: bool = False


class PageDetails(BaseModel):
    page_index: int
    image_path: str
    image_size: tuple[int, int]
    text_content: str | None = None
    metadata: PageMetadata | None = None


class TokenCount(BaseModel):
    model_name: str
    page_no: str
    request_tokens: int
    response_tokens: int


class PageGroup(BaseModel):
    group_name: str = Field(..., description="Use The Invoice Number as Group Name")
    page_indices: list[str] = Field(
        ...,
        description="List of page indices that belong to this invioice group , e.g., [P2, P3, P4]",
        default_factory=list,
    )

    @property
    def pages(self) -> list[int]:
        return [int(re.search(r"P(\d+)", page).group(1)) for page in self.page_indices]

    @property
    def size(self) -> int:
        return len(self.page_indices)

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
        text_content = []
        group = self.page_group_info[group_index]
        pages_content = [
            PAGE_TEMPLATE.substitute(
                page_no=p_data.page_index, page_content=p_data.text_content
            )
            for p_data in self.page_details
            if p_data.page_index in group.pages
        ]
        if group.is_multi_page:
            page_group_content = "\n".join(pages_content)
        else:
            page_group_content = pages_content[0] if pages_content else ""
        return page_group_content


def extract_page_num(file: Path) -> int:
    match = re.search(r"Page_(\d+)\.png", file.name)
    return int(match.group(1)) if match else 1000000


@dataclass
class SinglePageFormaterNode(BaseNode[WorkflowState, None]):
    page_numbers: list[int]

    async def run(self, ctx: GraphRunContext[WorkflowState, None]) -> End[Invoice]:
        agent = Agent(
            model=OpenAIModel(config.model3_name),
            system_prompt=SYSTEM_MESSAGE_3,
            output_type=Invoice,
            retries=5,
            model_settings={"temperature": 0.2},
        )
        logger.info("Running Single Page Formatter Node")
        self.semaphore = asyncio.Semaphore(config.max_concurrent_request)

        async def _get_agent_response(page_content: str) -> Invoice:
            async with self.semaphore:
                logger.info("Agent3 Processing Page Content")
                input_msg = USER_MESSAGE_1.substitute(page_content=page_content)
                result = agent.run(user_prompt=input_msg)
                token_expenditure = TokenCount(
                    model_name=agent.model.model_name,
                    page_no=f"1-{ctx.state.page_count}",
                    request_tokens=result.usage().request_tokens,
                    response_tokens=result.usage().response_tokens,
                )
                ctx.state.token_count.append(token_expenditure)
                return result.output

        task_list = [
            _get_agent_response(p_data.text_content)
            for p_data in ctx.state.page_details
            if p_data.page_index in self.page_numbers
        ]
        try:
            results = await asyncio.gather(*task_list)
        except Exception as err:
            logger.error(f"Error in Agent {agent.model.model_name} Response - {err!s}")
            return End(error=str(err))
        ctx.state.final_output.extend([result.output for result in results])
        if ctx.state.page_count == 1:
            return End(final_output=ctx.state.final_output)
        return End(final_output=result.output)


@dataclass
class PageGrouperNode(BaseNode[WorkflowState, None]):
    input_task: str = "page_grouping"

    async def run(self, ctx: GraphRunContext[WorkflowState, None]) -> None:
        logger.info("Running Page Grouping")
        agent = Agent(
            model=OpenAIModel(config.model2_name),
            system_prompt=SYSTEM_MESSAGE_2,
            output_type=PageGroupInfo,
            retries=2,
            model_settings={"temperature": 1},
        )
        page_metadata = {
            f"P{p_data.page_index}": p_data.metadata
            for p_data in ctx.state.page_details
        }
        message = USER_MESSAGE_2.substitute(PAGE_METADATA=str(page_metadata))
        result = await agent.run(user_prompt=message)
        token_expenditure = TokenCount(
            model_name=agent.model.model_name,
            page_no=f"1-{ctx.state.page_count}",
            request_tokens=result.usage().request_tokens,
            response_tokens=result.usage().response_tokens,
        )
        ctx.state.token_count.append(token_expenditure)
        ctx.state.page_group_info = result.output.group_info
        logger.info(f"Page Grouping Result: {ctx.state.page_group_info!s}")
        single_page_invoice_index = [
            group.pages[0]
            for group in ctx.state.page_group_info
            if group.is_single_page
        ]

        multipage_invoice_index = [
            group.pages[0] for group in ctx.state.page_group_info if group.is_multi_page
        ]
        if single_page_invoice_index:
            SinglePageFormaterNode(page_numbers=single_page_invoice_index)
        if 
        for group in ctx.state.page_group_info:
            logger.info(
                f"Group Name: {group.group_name}, Pages: {group.page_indices!s}"
            )
            if group.is_single_page:
                # If the group is a single page, format it directly
                page_index = group.pages[0]
                SinglePageFormaterNode(input_task=str(page_index - 1))


@dataclass
class MetadataExtractionNode(BaseNode[WorkflowState, None]):
    input_task: str = "metadata_extraction"

    async def run(
        self, ctx: GraphRunContext[WorkflowState, None]
    ) -> End[str] | SinglePageFormaterNode | PageGrouperNode:
        logger.info("Running Metadata Extraction Node")
        not_a_invoice_data = True
        for p_data, _ in ctx.state.page_details:
            if "NO_INVOICE_FOUND" in p_data.text_content:
                logger.info(
                    f"Skipped the page {p_data.page_index} content - {p_data.text_content}"
                )
                p_data.metadata = PageMetadata(**DEFAULT_INVOICE_METADATA)
                continue
            not_a_invoice_data = False
            json_string = extract_json_from_text(p_data.text_content)
            logger.info(
                f"Extracted JSON from Agent1 Response for Page {p_data.page_index}: {json_string!s}"
            )
            page_metadata = (
                extract_invoice_metadata(json_string)
                if json_string is not None
                else str(DEFAULT_INVOICE_METADATA)
            )
            p_data.text_content = re.sub(
                r"(?i)```json\s*{.*?}\s*```", "", p_data.text_content, flags=re.DOTALL
            )
            p_data.metadata = PageMetadata(**page_metadata)
        if not_a_invoice_data:
            End(error="No valid invoice data found in the provided pages.")
        if ctx.state.page_count == 1:
            SinglePageFormaterNode(input_task="1")
        PageGrouperNode(input_task="page_grouping")


@dataclass
class ImageTextExtractionNode(BaseNode[WorkflowState, None]):
    input_task: str = "image_text_extraction"

    async def run(
        self, ctx: GraphRunContext[WorkflowState, None]
    ) -> MetadataExtractionNode:
        agent = Agent(
            model=BedrockConverseModel(
                model_name=config.model1_name,
                provider=BedrockProvider(**get_secret_keys()),
            ),
            # model=OpenAIModel(cls.config.model2_name),
            system_prompt=SYSTEM_MESSAGE_1,
            output_type=str,
            retries=0,
            model_settings={"temperature": 0},
        )
        semaphore = asyncio.Semaphore(config.max_concurrent_request)

        async def _get_agent_response(
            page_details: PageDetails,
        ) -> tuple[PageDetails, TokenCount]:
            async with semaphore:
                logger.info(f"Agent1 Processing Page : {page_details.image_path.name}")
                img_byte, mimetype = image_to_byte_string(
                    page_details.image_path.resolve()
                )
                input_msg = [
                    USER_MESSAGE_1,
                    BinaryContent(data=img_byte, media_type=mimetype),
                ]
                result = await agent.run(user_prompt=input_msg)
                token_expenditure = TokenCount(
                    model_name=agent.model.model_name,
                    page_no=str(page_details.page_index),
                    request_tokens=result.usage().request_tokens,
                    response_tokens=result.usage().response_tokens,
                )
                page_details.text_content = result.output

                return page_details, token_expenditure

        task_list = [
            _get_agent_response(page_details.image_path, page_details.page_index)
            for page_details in ctx.state.page_details
        ]
        try:
            agent_response = await asyncio.gather(*task_list)
            agent_response.sort(key=lambda x: x[0].page_index)  # Sort by page index
        except Exception as err:
            logger.error(f"Error in Agent1 Response - {err!s}")
            return None
        ctx.state.page_details = [p_data for p_data, _ in agent_response]
        ctx.state.token_count = [t_count for _, t_count in agent_response]
        if not ctx.state.page_count == 1:
            return SinglePageFormaterNode(
                page_numbers=[p_data.page_index for p_data in ctx.state.page_details]
            )
        return MetadataExtractionNode()


@dataclass
class PDfToImageNode(BaseNode[WorkflowState, None]):
    input_task: str = "pdf_to_image"

    async def run(
        self, ctx: GraphRunContext[WorkflowState, None]
    ) -> ImageTextExtractionNode:
        converter = Pdf2ImgConverter.init_from_cfg(config)
        page_details = converter.run(ctx.state.pdf_name)
        page_details.sort(key=lambda x: extract_page_num(x[0]))  # Sort by page index
        ctx.state.page_details = [
            PageDetails(
                page_index=page_no,
                image_path=page_name,
                image_size=img_size,  # Placeholder, will be updated later
            )
            for page_no, page_name, img_size in enumerate(
                page_details, start=1
            )  # Start from 1 for page index
        ]

        return ImageTextExtractionNode()
