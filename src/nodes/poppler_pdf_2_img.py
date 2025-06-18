import asyncio
import logging
from collections.abc import AsyncGenerator
from pathlib import Path

from pdf2image import convert_from_path
from PIL.Image import Image

from src.config import InvoiceParserConfig

logger = logging.getLogger("asyncio")


class Pdf2ImgConverter:
    def __init__(self, cfg: InvoiceParserConfig) -> None:
        self.poppler_path: Path = Path(cfg.POPPLER_PATH) if cfg.POPPLER_PATH else Path()
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

    async def get_images(
        self, output_folder: Path, pdf_path: str | Path
    ) -> AsyncGenerator[tuple[Image, int, Path], None]:
        format_ = "png" if self.save_format == "png" else self.save_format
        images = await asyncio.to_thread(
            convert_from_path, pdf_path, dpi=600, poppler_path=self.poppler_path, fmt=format_
        )
        for index, image in enumerate(images, start=1):
            img_path = output_folder / f"Page_{index:04}.{format_}"
            yield image, index, img_path

    async def _resize_and_save(
        self, image: Image, page_index: int, output_path: Path
    ) -> tuple[int, Path, tuple[int, int]]:
        def process_and_save() -> tuple[int, Path, tuple[int, int]]:
            width, height = image.size
            save_format_ = "PNG" if self.save_format == "png" else self.save_format
            if not self.resize_ops_enabled:
                logger.info(f"Processing Page No {page_index} Images shape {image.size} ...")
                new_image = image.copy()
                new_image.save(output_path, save_format_)
                return page_index, output_path, new_image.size
            if width < height and height > self.max_height:
                new_height = self.max_height
                new_width = int(new_height * (width / height))
                new_image = image.resize((new_width, new_height))
                logger.info(f"Processing Page No {page_index} Images shape {new_image.size} ...")
                new_image.save(output_path, save_format_)
            elif width > height and width > self.max_width:
                new_width = self.max_width
                new_height = int(new_width * (height / width))
                new_image = image.resize((new_width, new_height))
                logger.info(f"Processing Page No {page_index} Images shape {new_image.size} ...")
                new_image.save(output_path, save_format_)
            else:
                logger.info(f"Processing Page No {page_index} Images shape {image.size} ...")
                new_image = image.copy()
                new_image.save(output_path, save_format_)
            return page_index, output_path, new_image.size

        return await asyncio.to_thread(process_and_save)

    def _resolve_conflict(self, subfolder: str) -> str:
        if not (self.output_path / Path(subfolder)).exists():
            return subfolder
        count = 0
        while True:
            count += 1
            if not (self.output_path / Path(f"{subfolder}_{count}")).exists():
                return f"{subfolder}_{count}"

    async def run(self, pdf_path: str | Path) -> tuple[Path, list[tuple[int, Path, tuple[int, int]]]]:
        if not Path(pdf_path).exists():  # type: ignore[reportOptionalMemberAccess]
            logger.info(f"PDF file {pdf_path} does not exist.")
            raise FileNotFoundError(f"PDF file {pdf_path} does not exist.")
        filename = Path(pdf_path).stem
        filename = self._resolve_conflict(filename)
        output_folder = self.output_path / Path(filename)
        output_folder.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output Folder {output_folder} ")

        results, tasks = [], []
        try:
            async for image, page_index, img_path in self.get_images(output_folder, str(pdf_path)):
                tasks.append(self._resize_and_save(image, page_index, img_path))
                # Process in smaller batches to avoid memory issues
                if len(tasks) >= self.batch_size:  # Adjust batch size as needed
                    output_t = await asyncio.gather(*tasks)
                    results.extend(output_t)
                    tasks = []
            if tasks:
                output_t = await asyncio.gather(*tasks)
                results.extend(output_t)
                tasks = []
        except Exception as e:
            logger.error(f"Error While Processing Pdf str{e}")
        return output_folder, results
