from asyncio.log import logger
from dataclasses import dataclass

from pydantic_graph import BaseNode, End, Graph, GraphRunContext

from src.config import config
from src.nodes import (
    ImageToTextConverter,
    PageGroupper,
    Pdf2ImgConverter,
    SinglePageFormator,
)
from src.output_format import Invoice
from src.state import (
    PageDetails,
    PageGroup,
    WorkflowState,
)


@dataclass
class PageFormatterNode(BaseNode[WorkflowState, None, list[Invoice]]):
    task_type: str = "simple"

    async def run(self, ctx: GraphRunContext[WorkflowState, None]) -> End[list[Invoice]]:
        page_formatter = SinglePageFormator(config)
        response = await page_formatter.run(
            [
                (p_data.page_index, p_data.append_page_no(), p_data.metadata)
                for p_data in ctx.state.page_details
                if p_data.is_invoice_page
            ]
        )
        for invoice, t_count in response:
            ctx.state.token_count.append(t_count)
            ctx.state.final_output.append(invoice)
        return End(data=ctx.state.final_output)


@dataclass
class PageGrouperNode(BaseNode[WorkflowState, None]):
    async def run(self, ctx: GraphRunContext[WorkflowState, None]) -> PageFormatterNode:
        logger.info("Running Page Grouping")
        agent = PageGroupper(config)
        page_metadata = {
            f"P{p_data.page_index}": p_data.metadata for p_data in ctx.state.page_details if p_data.is_invoice_page
        }
        page_index = "-".join([p_data.page_index for p_data in ctx.state.page_details])
        page_group_info, token_expenditure = await agent.run(page_metadata=page_metadata, page_no=page_index)
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
    async def run(self, ctx: GraphRunContext[WorkflowState, None]) -> End[str] | PageFormatterNode | PageGrouperNode:
        agent = ImageToTextConverter(config)
        agent_response = await agent.run(ctx.state.image_dir)

        for p_no, text_content, meta_data, t_count in agent_response:
            ctx.state.token_count.append(t_count)
            for p_data in ctx.state.page_details:
                if p_data.page_index == p_no:
                    p_data.text_content = text_content
                    p_data.metadata = meta_data
        if ctx.state.valid_invoice_count() == 0:
            return End(error="No valid invoice data found in the provided PDF.")
        if ctx.state.valid_invoice_count() == ctx.state.unique_invoice_count():
            logger.info("All pages are single page invoices.")
            return PageFormatterNode(task_type="simple")
        logger.info("Multiple page invoices detected, proceeding to page grouping.")
        return PageGrouperNode()


@dataclass
class PdfToImageNode(BaseNode[WorkflowState, None]):
    input_task: str = "pdf_to_image"

    async def run(self, ctx: GraphRunContext[WorkflowState, None]) -> TextExtractionNode:
        converter = Pdf2ImgConverter(config)
        image_directort, page_details = await converter.run(ctx.state.pdf_name)
        ctx.state.image_dir = image_directort
        for page_no, page_name, img_size in page_details:
            ctx.state.page_details = [
                PageDetails(
                    page_index=page_no,
                    image_path=page_name.name,
                    image_size=img_size,
                )
            ]
        return TextExtractionNode()


workflow = Graph(nodes=[PdfToImageNode, TextExtractionNode, PageGrouperNode, PageFormatterNode])


async def run_workflow(pdf_name: str) -> WorkflowState:
    """
    Run the workflow to process the PDF and extract invoice information.
    """
    initial_state = WorkflowState(pdf_name=str(pdf_name))
    initial_state.pdf_name = str(pdf_name)

    logger.info(f"Starting workflow for PDF: {pdf_name}")
    result = await workflow.run(PdfToImageNode(pdf_name), state=initial_state)

    logger.info(f"Workflow failed with error: {result.data!s}")

    return result.data
