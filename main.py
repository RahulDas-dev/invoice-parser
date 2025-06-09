import asyncio
import logging
from pathlib import Path
from src.config import config
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def run_pdf_to_image_conversion():
    from src.nodes import Pdf2ImgConverter

    converter = Pdf2ImgConverter(config)
    output_path, page_data = await converter.run("Invoice-Copy-20.pdf")
    logging.info(f"Output Path: {output_path}")
    logging.info(f"Page Data: {page_data}")
    return None


async def run_image_to_text_conversion():
    from src.nodes import ImageToTextConverter

    converter = ImageToTextConverter(config)
    page_data = await converter.run(
        Path("D:/output/invoice_parser/pdf2img/Invoice-Copy-20")
    )
    logging.info(f"Page Data: {page_data}")
    return None


async def run_page_groupper():
    from src.nodes import ImageToTextConverter
    from src.nodes import PageGroupper

    converter = ImageToTextConverter(config)
    page_data = await converter.run(
        Path("D:/output/invoice_parser/pdf2img/Invoice-Copy-20")
    )
    page_metadata = {
        f"P{page_index}": metadata for page_index, _, metadata, _ in page_data
    }
    page_no = "-".join([str(page_index) for page_index, _, _, _ in page_data])
    groupper = PageGroupper(config)
    group_meta, t_count = await groupper.run(page_metadata, page_no)
    logging.info(f"Group MetaData: {group_meta}")
    return None


if __name__ == "__main__":
    asyncio.run(run_page_groupper())
