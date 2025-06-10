import asyncio
from asyncio.log import logger
from pathlib import Path

import pypdfium2 as pdfium
from pypdfium2._helpers import PdfBitmap

from src.config import InvoiceParserConfig
from src.utility import async_range


class Pdf2ImgConverter:
    def __init__(self, cfg: InvoiceParserConfig) -> None:
        self.input_path: Path = cfg.INPUT_PATH
        self.output_path: Path = Path(cfg.OUTPUT_PATH) / "pdf2img"
        if not self.output_path.exists():
            self.output_path.mkdir(parents=True)
        self.max_width: int = cfg.MAX_IMG_WIDTH
        self.max_height: int = cfg.MAX_IMG_HEIGHT
        self.batch_size: int = cfg.MAX_CONCURRENT_REQUEST
        self.save_format: str = cfg.IMG_SAVE_FORMAT

    @property
    def resize_ops_enabled(self) -> bool:
        return self.max_width > 0 and self.max_height > 0

    async def _convert_to_image_and_save(
        self, page_bitmap: PdfBitmap, page_index: int, output_folder: Path
    ) -> tuple[int, Path, tuple[int, int]]:
        def process_and_save() -> tuple[int, Path, tuple[int, int]]:
            pil_image = page_bitmap.to_pil()
            save_format_ = "PNG" if self.save_format == "png" else self.save_format
            save_path = output_folder / f"Page_{page_index:04}.png"
            if not self.resize_ops_enabled:
                logger.info(f"Processing Page No {page_index} Images shape {pil_image.size} ...")
                new_image = pil_image
                new_image.save(save_path, save_format_)
            else:
                width, height = pil_image.size
                if width < height and height > self.max_height:
                    new_height = self.max_height
                    new_width = int(new_height * (width / height))
                    new_image = pil_image.resize((new_width, new_height))
                    logger.info(f"Processing Page No {page_index} Images shape {new_image.size} ...")
                    new_image.save(save_path, save_format_)
                elif width > height and width > self.max_width:
                    new_width = self.max_width
                    new_height = int(new_width * (height / width))
                    new_image = pil_image.resize((new_width, new_height))
                    logger.info(f"Processing Page No {page_index} Images shape {new_image.size} ...")
                    new_image.save(save_path, save_format_)
                else:
                    logger.info(f"Processing Page No {page_index} Images shape {pil_image.size} ...")
                    new_image = pil_image
                    new_image = pil_image.save(save_path, save_format_)
            return page_index, save_path, new_image.size

        return await asyncio.to_thread(process_and_save)

    def _resolve_conflict(self, subfolder: str) -> str:
        if not (self.output_path / Path(subfolder)).exists():
            return subfolder
        count = 0
        while True:
            count += 1
            if not (self.output_path / Path(f"{subfolder}_{count}")).exists():
                return f"{subfolder}_{count}"

    async def run(self, pdf_name: str | Path) -> tuple[Path, list[tuple[int, Path, tuple[int, int]]]]:
        pdf_path = self.input_path / pdf_name
        if not pdf_path.exists():  # type: ignore[reportOptionalMemberAccess]
            logger.info(f"PDF file {pdf_path} does not exist.")
            raise FileNotFoundError(f"PDF file {pdf_path} does not exist.")
        filename = Path(pdf_path).stem
        filename = self._resolve_conflict(filename)
        output_folder = self.output_path / Path(filename)
        output_folder.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output Folder {output_folder} ")
        pdf_doc = pdfium.PdfDocument(pdf_path)
        page_count = len(pdf_doc)
        logger.info(f"Pdf Document Page count {page_count} ")

        results = []
        try:
            tasks = []
            async for page_index in async_range(page_count):
                tasks.append(
                    self._convert_to_image_and_save(
                        pdf_doc[page_index].render(scale=3, rotation=0),
                        page_index + 1,
                        output_folder,
                    )
                )
                # Process in smaller batches to avoid memory issues
                if len(tasks) >= self.batch_size:  # Adjust batch size as needed
                    output_t = await asyncio.gather(*tasks)
                    results.extend(output_t)
                    tasks = []
            # Process any remaining tasks
            if tasks:
                output_t = await asyncio.gather(*tasks)
                results.extend(output_t)
                tasks = []
        except Exception as e:
            logger.error(f"Error While Processing Pdf str{e}")
        return output_folder, results
