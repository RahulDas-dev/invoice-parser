# ruff: noqa: LOG015, T203
import asyncio
import logging
from pathlib import Path
from pprint import pprint

from dotenv import load_dotenv

from src.config import app_config

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def run_pdf_to_image_conversion() -> None:
    from src.nodes import Pdf2ImgConverter

    converter = Pdf2ImgConverter(app_config)
    output_path, page_data = await converter.run("Invoice-Copy-20.pdf")
    logging.info(f"Output Path: {output_path}")
    logging.info(f"Page Data: {page_data}")


async def run_image_to_text_conversion() -> None:
    from src.nodes import ImageToTextConverter

    converter = ImageToTextConverter(app_config)
    page_data = await converter.run(Path("D:/output/invoice_parser/pdf2img/Invoice-Copy-20"))
    logging.info(f"Page Data: {page_data}")


async def run_page_groupper() -> None:
    from src.nodes import ImageToTextConverter, PageGroupper

    converter = ImageToTextConverter(app_config)
    page_data = await converter.run(Path("D:/output/invoice_parser/pdf2img/Invoice-Copy-20"))
    page_metadata = {f"P{page_index}": metadata for page_index, _, metadata, _ in page_data}
    pprint(page_metadata)
    page_no = "-".join([str(page_index) for page_index, _, _, _ in page_data])
    groupper = PageGroupper(app_config)
    group_meta, t_count = await groupper.run(page_metadata, page_no)
    pprint(group_meta)


async def run_end2end_workflow() -> None:
    from src.workflow import iter_workflow, run_workflow

    # result = await run_workflow(Path("Invoice-Copy-20.pdf"))
    result = await iter_workflow(Path("D:/datasets/invoice_pdf/642265.pdf"))
    logging.info(f"Workflow Result: {result}")


if __name__ == "__main__":
    asyncio.run(run_end2end_workflow())
