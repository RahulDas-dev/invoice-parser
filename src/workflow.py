from dataclasses import dataclass
from asyncio.log import logger
from pydantic_graph import BaseNode, End, Graph, GraphRunContext

from nodes import (
    ImageToTextConverter,
    MultiPageFormator,
    SinglePageFormator,
    PageGroupper,
    Pdf2ImgConverter,
)
from config import config
from output_format import Invoice
from utility import extract_page_no

from state import (
    PageDetails,
    PageGroup,
    WorkflowState,
)


@dataclass
class PageFormatterNode(BaseNode[WorkflowState, None, list[Invoice]]):
    async def run(
        self, ctx: GraphRunContext[WorkflowState, None]
    ) -> End[list[Invoice]]:
        if not ctx.state.page_count == 1:
            page_formatter = SinglePageFormator(config)
            response = await page_formatter.run(
                [
                    (p_data.page_no, p_data.text_content, p_data.metadata)
                    for p_data in ctx.state.page_details
                ]
            )
            for invoice, t_count in response:
                ctx.state.token_count.append(t_count)
                ctx.state.final_output.append(invoice)
            return End(
                output=ctx.state.final_output,
                message="Single Page Invoice Formatted Successfully",
            )
        single_page_invoice_index = [
            group.pages[0]
            for group in ctx.state.page_group_info
            if group.is_single_page
        ]

        multipage_invoice_index = [
            group.pages[0] for group in ctx.state.page_group_info if group.is_multi_page
        ]
        if single_page_invoice_index:
            spage_formatter = SinglePageFormator(config)
            response = await spage_formatter.run(
                [
                    (p_data.page_no, p_data.text_content, p_data.metadata)
                    for p_data in ctx.state.page_details
                    if p_data.page_index in single_page_invoice_index
                ]
            )
            for invoice, t_count in response:
                ctx.state.token_count.append(t_count)
                ctx.state.final_output.append(invoice)

        if multipage_invoice_index:
            mpage_formatter = MultiPageFormator(config)
            response = await mpage_formatter.run(
                [
                    (p_data.page_no, p_data.text_content, p_data.metadata)
                    for p_data in ctx.state.page_details
                    if p_data.page_index in multipage_invoice_index
                ]
            )
            for invoice, t_count in response:
                ctx.state.token_count.append(t_count)
                ctx.state.final_output.append(invoice)

        return End(
            output=ctx.state.final_output,
            message="Single Page Invoice Formatted Successfully",
        )


@dataclass
class PageGrouperNode(BaseNode[WorkflowState, None]):
    async def run(self, ctx: GraphRunContext[WorkflowState, None]) -> PageFormatterNode:
        logger.info("Running Page Grouping")
        agent = PageGroupper(config)
        page_metadata = {
            f"P{p_data.page_index}": p_data.metadata
            for p_data in ctx.state.page_details
        }
        page_index = "-".join([p_data.page_index for p_data in ctx.state.page_details])
        page_group_info, token_expenditure = await agent.run(
            page_metadata=page_metadata, page_no=page_index
        )
        ctx.state.token_count.append(token_expenditure)
        logger.info(f"Page Grouping Result: {page_group_info!s}")
        for key, value in page_group_info.items():
            logger.info(f"Key: {key}, Value: {value!s}")
            ctx.state.page_group_info.append(
                PageGroup(
                    group_name=key,
                    page_indices=value["pages"],
                    details=value.get("details", {}),
                )
            )
        return PageFormatterNode()


@dataclass
class TextExtractionNode(BaseNode[WorkflowState, None]):
    async def run(
        self, ctx: GraphRunContext[WorkflowState, None]
    ) -> End[str] | PageFormatterNode | PageGrouperNode:
        agent = ImageToTextConverter(config)
        agent_response = await agent.run(ctx.state.pdf_name)

        for pa_no, text_content, meta_data, t_count in agent_response:
            ctx.state.token_count.append(t_count)
            page_details = next(
                [
                    p_data
                    for p_data in ctx.state.page_details
                    if p_data.page_index == pa_no
                ]
            )
            page_details.text_content = text_content
            page_details.metadata = meta_data
        not_a_invoice_data = True
        for p_data in ctx.state.page_details:
            if "NO_INVOICE_FOUND" in p_data.text_content:
                logger.info(
                    f"Skipped the page {p_data.page_index} content - {p_data.text_content}"
                )
                not_a_invoice_data = False
        if not_a_invoice_data:
            return End(error="No valid invoice data found in the provided PDF.")
        if ctx.state.page_count == 1:
            return PageFormatterNode()
        return PageGrouperNode()


@dataclass
class PdfToImageNode(BaseNode[WorkflowState, None]):
    input_task: str = "pdf_to_image"

    async def run(
        self, ctx: GraphRunContext[WorkflowState, None]
    ) -> TextExtractionNode:
        converter = Pdf2ImgConverter.init_from_cfg(config)
        page_details = converter.run(ctx.state.pdf_name)

        for page_name, img_size in page_details:
            # Assuming extract_page_num is a function that extracts the page number from the filename
            page_no = extract_page_no(page_name, image_ext=config.image_ext)
            ctx.state.page_details = [
                PageDetails(
                    page_index=page_no,
                    image_path=page_name,
                    image_size=img_size,  # Placeholder, will be updated later
                )
            ]

        return TextExtractionNode()


workflow = Graph(
    nodes=[PdfToImageNode, TextExtractionNode, PageGrouperNode, PageFormatterNode]
)


def run_workflow(pdf_name: str) -> WorkflowState:
    """
    Run the workflow to process the PDF and extract invoice information.
    """
    initial_state = WorkflowState(pdf_name=str(pdf_name))
    initial_state.pdf_name = str(pdf_name)

    logger.info(f"Starting workflow for PDF: {pdf_name}")
    result = workflow.run(PdfToImageNode(pdf_name), state=initial_state)

    if result.error:
        logger.error(f"Workflow failed with error: {result.error}")
        raise Exception(result.error)

    logger.info("Workflow completed successfully.")
    return result.state
