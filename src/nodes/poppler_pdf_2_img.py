import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        self.dpi: int = 600  # Lower DPI for faster processing

    @property
    def resize_ops_enabled(self) -> bool:
        return self.max_width > 0 and self.max_height > 0

    def _convert_pdf_pages(self, pdf_path: str | Path, first_page: int, last_page: int) -> list[Image]:
        """Convert a range of PDF pages to images"""
        format_ = "png" if self.save_format == "png" else self.save_format
        return convert_from_path(
            pdf_path,
            dpi=self.dpi,
            poppler_path=self.poppler_path,
            fmt=format_,
            first_page=first_page,
            last_page=last_page,
            thread_count=last_page - first_page + 1,  # Enable multithreading in poppler
        )

    def _process_and_save_image(
        self, image: Image, page_index: int, output_path: Path
    ) -> tuple[int, Path, tuple[int, int]]:
        """Process and save an image, with optional resizing"""
        width, height = image.size
        save_format_ = "PNG" if self.save_format == "png" else self.save_format

        try:
            if not self.resize_ops_enabled:
                logger.info(f"Processing Page No {page_index} Images shape {image.size} ...")
                image.save(output_path, save_format_, optimize=True)
                return (page_index, output_path, image.size)

            if width < height and height > self.max_height:
                new_height = self.max_height
                new_width = int(new_height * (width / height))
                new_image = image.resize((new_width, new_height))
                logger.info(f"Processing Page No {page_index} Images shape {new_image.size} ...")
                new_image.save(output_path, save_format_, optimize=True)
                size = new_image.size
                return (page_index, output_path, size)

            if width > height and width > self.max_width:
                new_width = self.max_width
                new_height = int(new_width * (height / width))
                new_image = image.resize((new_width, new_height))
                logger.info(f"Processing Page No {page_index} Images shape {new_image.size} ...")
                new_image.save(output_path, save_format_, optimize=True)
                size = new_image.size
                return (page_index, output_path, size)
            logger.info(f"Processing Page No {page_index} Images shape {image.size} ...")
            image.save(output_path, save_format_, optimize=True)
            return (page_index, output_path, image.size)
        finally:
            # Force Python garbage collection on the image object
            if "new_image" in locals():
                del new_image

    def _resolve_conflict(self, subfolder: str) -> str:
        if not (self.output_path / Path(subfolder)).exists():
            return subfolder
        count = 0
        while True:
            count += 1
            if not (self.output_path / Path(f"{subfolder}_{count}")).exists():
                return f"{subfolder}_{count}"

    def _get_pdf_page_count(self, pdf_path: str | Path) -> int:
        """Get the number of pages in a PDF file"""
        from pdf2image.pdf2image import pdfinfo_from_path

        info = pdfinfo_from_path(str(pdf_path), poppler_path=str(self.poppler_path))
        return info["Pages"]

    async def run(self, pdf_path: str | Path) -> tuple[Path, list[tuple[int, Path, tuple[int, int]]]]:
        """Convert PDF to images using ThreadPoolExecutor for parallel processing"""
        if not Path(pdf_path).exists():
            logger.info(f"PDF file {pdf_path} does not exist.")
            raise FileNotFoundError(f"PDF file {pdf_path} does not exist.")
        filename = self._resolve_conflict(Path(pdf_path).stem)
        output_folder = self.output_path / Path(filename)
        output_folder.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output Folder {output_folder}")
        page_count = self._get_pdf_page_count(pdf_path)
        logger.info(f"PDF has {page_count} pages")
        format_ = "png" if self.save_format == "png" else self.save_format
        results = []
        max_workers_ = os.cpu_count() or 4
        batch_size = self._calculate_batch_size(page_count, max_workers_)
        with ThreadPoolExecutor(max_workers=max_workers_) as executor:
            batch_futures = {}
            for start_page in range(1, page_count + 1, batch_size):
                end_page = min(start_page + batch_size - 1, page_count)
                future = executor.submit(self._convert_pdf_pages, pdf_path, start_page, end_page)
                batch_futures[future] = (start_page, end_page)
            image_futures = []
            self._process_batch_conversions(executor, batch_futures, image_futures, output_folder, format_)
            self._collect_image_results(image_futures, results)
        results.sort(key=lambda x: x[0])
        return output_folder, results

    def _calculate_batch_size(self, page_count: int, available_workers: int) -> int:
        """Calculate optimal batch size based on available workers and total pages

        This optimizes the batch size to maximize parallelism while avoiding excessive memory usage
        """
        # For small documents, process each page individually for maximum parallelism
        small_docs_pages, medium_docs_pages, large_docs_pages = 5, 20, 50
        if page_count <= small_docs_pages:
            return 1

        # For medium documents, balance batch size with available workers
        if page_count <= medium_docs_pages:
            return max(1, min(3, page_count // available_workers))

        # For larger documents, use larger batches to reduce overhead
        if page_count <= large_docs_pages:
            return max(2, min(5, page_count // available_workers))

        # For very large documents, use even larger batches to manage memory usage
        # but ensure we don't go below a reasonable minimum batch size
        return max(3, min(self.batch_size, page_count // (available_workers * 2)))

    def _process_batch_conversions(
        self, executor: ThreadPoolExecutor, batch_futures: dict, image_futures: list, output_folder: Path, format_: str
    ) -> None:
        """Process PDF batch conversions and create image processing tasks"""
        for future in as_completed(batch_futures):
            try:
                start_page, _ = batch_futures[future]
                images = future.result()
                for page_index, image in enumerate(images, start=start_page):
                    # page_index = start_page + i
                    img_path = output_folder / f"Page_{page_index:04}.{format_}"
                    page_future = executor.submit(self._process_and_save_image, image, page_index, img_path)
                    image_futures.append(page_future)
            except Exception as e:  # noqa: PERF203
                logger.error(f"Error processing batch: {e!s}")

    def _collect_image_results(self, image_futures: list, results: list) -> None:
        """Collect image processing results"""
        for future in as_completed(image_futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:  # noqa: PERF203
                logger.error(f"Error processing image: {e!s}")
