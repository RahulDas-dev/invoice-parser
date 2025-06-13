from asyncio.log import logger
from dataclasses import dataclass
from pathlib import Path

from pydantic_graph import BaseNode, End, Graph, GraphRunContext

from src.config import app_config

from .nodes import ImageToTextConverter, PageAggregator, PageGroupper, Pdf2ImgConverter, SinglePageFormator
from .state import (
    PageDetails,
    PageGroup,
    WorkflowState,
)


@dataclass
class PageAggregatorNode(BaseNode[WorkflowState, None, str]):
    async def run(self, ctx: GraphRunContext[WorkflowState, None]) -> End[str]:
        logger.info("Running Page Aggregation")
        agent = PageAggregator(app_config)
        for group in ctx.state.page_group_info:
            pages_2_process = group.pages
            invoices_2_process = [
                p_data.invoice
                for p_data in ctx.state.page_details
                if p_data.page_index in pages_2_process and p_data.invoice is not None
            ]
            if len(invoices_2_process) == 1:
                ctx.state.final_output.append(invoices_2_process[0])
                continue
            invoice = await agent.run(invoices=invoices_2_process, merger_stratagy=group.details)
            ctx.state.final_output.append(invoice)
        return End(data="Processing Completed")


@dataclass
class PageFormatterNode(BaseNode[WorkflowState, None, str]):
    task_type: str = "simple"

    async def run(self, ctx: GraphRunContext[WorkflowState, None]) -> End[str] | PageAggregatorNode:
        page_formatter = SinglePageFormator(app_config)

        response, error = await page_formatter.run(
            [
                (p_data.page_index, p_data.append_page_no(), dict(p_data.metadata))
                for p_data in ctx.state.page_details
                if p_data.is_invoice_page
            ]
        )
        if error:
            ctx.state.error = f"PageFormatterNode| {error}"
            return End(data=ctx.state.error)
        for page_no, invoice, t_count in response:
            ctx.state.token_count.append(t_count)
            for page_detail in ctx.state.page_details:
                if page_detail.page_index == page_no:
                    page_detail.invoice = invoice
                    break
            if self.task_type == "simple":
                ctx.state.final_output.append(invoice)
        if self.task_type == "simple":
            return End(data="Processing Completed")
        return PageAggregatorNode()


@dataclass
class PageGrouperNode(BaseNode[WorkflowState, None, str]):
    async def run(self, ctx: GraphRunContext[WorkflowState, None]) -> PageFormatterNode | End[str]:
        logger.info("Running Page Grouping")
        agent = PageGroupper(app_config)
        page_metadata = {
            f"P{p_data.page_index}": p_data.metadata for p_data in ctx.state.page_details if p_data.is_invoice_page
        }
        page_index = "-".join([str(p_data.page_index) for p_data in ctx.state.page_details])
        page_group_info, token_expenditure, error = await agent.run(page_metadata=page_metadata, page_no=page_index)
        if error:
            ctx.state.error = f"PageGrouperNode| {error}"
            return End(data=error)
        ctx.state.token_count.append(token_expenditure)
        logger.info(f"Page Grouping Result: {page_group_info!s}")
        for key, value in page_group_info.items():
            logger.info(f"Key: {key}, Value: {value!s}")
            ctx.state.page_group_info.append(
                PageGroup(
                    group_name=key,
                    page_nos=value["pages"],
                    details=value.get("details", {}),
                )
            )
        return PageFormatterNode(task_type="complex")


@dataclass
class TextExtractionNode(BaseNode[WorkflowState, None, str]):
    async def run(self, ctx: GraphRunContext[WorkflowState, None]) -> End[str] | PageFormatterNode | PageGrouperNode:
        agent = ImageToTextConverter(app_config)
        agent_response, error = await agent.run(ctx.state.image_dir)
        if error:
            ctx.state.error = f"TextExtractionNode| {error}"
            return End(data=error)
        for p_no, text_content, meta_data, t_count in agent_response:
            ctx.state.token_count.append(t_count)
            for p_data in ctx.state.page_details:
                if p_data.page_index == p_no:
                    p_data.text_content = text_content
                    p_data.metadata = meta_data
                    break
        valid_invoices_count = ctx.state.valid_invoice_count()
        unique_invoices_count = ctx.state.unique_invoice_count()
        logger.info(f"Valid Invoices Count: {valid_invoices_count}, Unique Invoices Count: {unique_invoices_count}")
        if valid_invoices_count == 0:
            ctx.state.error = "No valid invoice data found in the provided PDF."
            return End(data=ctx.state.error)
        if valid_invoices_count == unique_invoices_count:
            logger.info("All pages are single page invoices.")
            return PageFormatterNode(task_type="simple")
        logger.info("Multiple page invoices detected, proceeding to page grouping.")
        return PageGrouperNode()


@dataclass
class PdfToImageNode(BaseNode[WorkflowState, None]):
    pdf_path: Path

    async def run(self, ctx: GraphRunContext[WorkflowState, None]) -> TextExtractionNode:
        converter = Pdf2ImgConverter(app_config)
        image_directory, page_details = await converter.run(self.pdf_path)
        ctx.state.image_dir = str(image_directory)
        for page_no, page_name, img_size in page_details:
            ctx.state.page_details.append(
                PageDetails(
                    page_index=page_no,
                    image_path=page_name.name,
                    image_size=img_size,
                )
            )
        return TextExtractionNode()


workflow = Graph(nodes=[PdfToImageNode, TextExtractionNode, PageGrouperNode, PageFormatterNode, PageAggregatorNode])


async def run_workflow(pdf_path: Path) -> WorkflowState:
    """
    Run the workflow to process the PDF and extract invoice information.
    """
    initial_state = WorkflowState(pdf_name=pdf_path.name)

    logger.info(f"Starting workflow for PDF: {pdf_path.name}")
    try:
        _ = await workflow.run(PdfToImageNode(pdf_path), state=initial_state)
    except Exception as e:
        logger.error(f"Workflow failed with error: {e!s}")
        initial_state.error = str(e)
    return initial_state


async def iter_workflow(pdf_path: Path) -> WorkflowState:
    """
    Run the workflow to process the PDF and extract invoice information.
    """
    initial_state = WorkflowState(pdf_name=pdf_path.name)

    logger.info(f"Starting workflow for PDF: {pdf_path.name}")
    try:
        async with workflow.iter(PdfToImageNode(pdf_path), state=initial_state) as run:
            async for node in run:
                logger.info(f"Node: {node.__class__.__name__}")
                if isinstance(node, End):
                    logger.info(f"returned data: {node.data!s}")
                logger.info("------------------------------------------")
    except Exception as e:
        logger.error(f"Workflow failed with error: {e!s}")
        initial_state.error = str(e)
        return initial_state
    logger.info(f"Workflow completed successfully. Final invoice count: {len(initial_state.final_output)}")
    return initial_state
