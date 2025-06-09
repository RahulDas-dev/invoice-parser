import logging
from src.config import config

from nodes.pdf_2_image import Pdf2ImgConverter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


if __name__ == "__main__":
    converter = Pdf2ImgConverter.init_from_cfg(config)
    converter.run("Invoice-Copy-20.pdf")
