from dataclasses import dataclass
from asyncio.log import logger
from pydantic_graph import BaseNode, End, Graph, GraphRunContext

from src.nodes import (
    ImageToTextConverter,
    MultiPageFormator,
    SinglePageFormator,
    PageGroupper,
    Pdf2ImgConverter,
)
from src.config import config
from src.output_format import Invoice
from src.utility import extract_page_no

from src.state import (
    PageDetails,
    PageGroup,
    WorkflowState,
)


@dataclass
class PageFormatterNode(BaseNode[WorkflowState, None, list[Invoice]]):
    task_type: str = "simple"

    async def _simple_run(
        self, ctx: GraphRunContext[WorkflowState, None]
    ) -> End[list[Invoice]]:
        page_formatter = SinglePageFormator(config)
        response = await page_formatter.run(
            [
                (p_data.page_index, p_data.text_content, p_data.metadata)
                for p_data in ctx.state.page_details
                if p_data.is_invoice_page
            ]
        )
        for invoice, t_count in response:
            ctx.state.token_count.append(t_count)
            ctx.state.final_output.append(invoice)
        return End(data=ctx.state.final_output)

    async def _complex_run(
        self, ctx: GraphRunContext[WorkflowState, None]
    ) -> End[list[Invoice]]:
        singlepage_invoice_index = [
            group.pages[0]
            for group in ctx.state.page_group_info
            if group.is_single_page
        ]

        multipage_invoice_index = [
            group.pages[0] for group in ctx.state.page_group_info if group.is_multi_page
        ]
        if singlepage_invoice_index:
            spage_formatter = SinglePageFormator(config)
            response = await spage_formatter.run(
                [
                    (p_data.page_no, p_data.text_content, p_data.metadata)
                    for p_data in ctx.state.page_details
                    if p_data.page_index in singlepage_invoice_index
                ]
            )
            for invoice, t_count in response:
                ctx.state.token_count.append(t_count)
                ctx.state.final_output.append(invoice)

        if multipage_invoice_index:
            mpage_formatter = MultiPageFormator(config)
            response = await mpage_formatter.run(
                [
                    (p_data.page_no, p_data.append_page_no(), p_data.metadata)
                    for p_data in ctx.state.page_details
                    if p_data.page_index in multipage_invoice_index
                ]
            )
            for invoice, t_count in response:
                ctx.state.token_count.append(t_count)
                ctx.state.final_output.append(invoice)

        return End(output=ctx.state.final_output)

    async def run(
        self, ctx: GraphRunContext[WorkflowState, None]
    ) -> End[list[Invoice]]:
        if self.task_type == "simple":
            return await self._simple_run(ctx)
        elif self.task_type == "complex":
            return await self._complex_run(ctx)


@dataclass
class PageGrouperNode(BaseNode[WorkflowState, None]):
    async def run(self, ctx: GraphRunContext[WorkflowState, None]) -> PageFormatterNode:
        logger.info("Running Page Grouping")
        agent = PageGroupper(config)
        page_metadata = {
            f"P{p_data.page_index}": p_data.metadata
            for p_data in ctx.state.page_details
            if p_data.is_invoice_page
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
        return PageFormatterNode(task_type="complex")


@dataclass
class TextExtractionNode(BaseNode[WorkflowState, None]):
    async def run(
        self, ctx: GraphRunContext[WorkflowState, None]
    ) -> End[str] | PageFormatterNode | PageGrouperNode:
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

    async def run(
        self, ctx: GraphRunContext[WorkflowState, None]
    ) -> TextExtractionNode:
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


workflow = Graph(
    nodes=[PdfToImageNode, TextExtractionNode, PageGrouperNode, PageFormatterNode]
)


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
