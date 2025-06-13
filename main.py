# ruff: noqa: LOG015, T203, T201
import asyncio
import logging
import sys
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


async def run_image_to_text_conversion(pdf_path: Path) -> None:
    from src.nodes import ImageToTextConverter

    converter = ImageToTextConverter(app_config)
    page_data = await converter.run(pdf_path)
    logging.info(f"Page Data: {page_data}")


async def run_page_groupper(pdf_path: Path) -> None:
    from src.nodes import ImageToTextConverter, PageGroupper

    converter = ImageToTextConverter(app_config)
    page_data, err = await converter.run(pdf_path)
    if err:
        logging.error(f"Error during image to text conversion: {err}")
        return
    page_metadata = {f"P{page_index}": metadata for page_index, _, metadata, _ in page_data}
    pprint(page_metadata)
    page_no = "-".join([str(page_index) for page_index, _, _, _ in page_data])
    groupper = PageGroupper(app_config)
    group_meta, _, err = await groupper.run(page_metadata, page_no)
    pprint(group_meta)


async def run_end2end_workflow(pdf_path: Path) -> None:
    from src.workflow import iter_workflow

    # result = await run_workflow(Path("Invoice-Copy-20.pdf"))
    result = await iter_workflow(pdf_path)
    logging.info(f"Workflow Result: {result}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python app.py <path_to_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]

    # Validate the path exists
    if not Path(pdf_path).is_file():
        print(f"Error: File not found at '{pdf_path}'")
        sys.exit(1)

    pdf_path = Path(pdf_path)
    asyncio.run(run_end2end_workflow(pdf_path))
