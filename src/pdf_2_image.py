import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

import pypdfium2 as pdfium
from pypdfium2._helpers import PdfBitmap

from src.config import InvoiceParserConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Pdf2ImgConverter:
    input_path: Path = field(default_factory=Path)
    output_path: Path = field(default_factory=Path)
    max_width: int = field(default=-1)
    max_height: int = field(default=-1)
    thread_count: int = field(default=1)
    save_format: str = field(default="png")

    @property
    def resize_ops_enabled(self) -> bool:
        return self.max_width > 0 and self.max_height > 0

    @classmethod
    def init_from_cfg(cls, cfg: InvoiceParserConfig) -> Self:
        output_path_ = Path(cfg.OUTPUT_PATH) / Path("pdf2img")
        if not output_path_.exists():
            output_path_.mkdir(parents=True)
        return Pdf2ImgConverter(
            input_path=cfg.INPUT_PATH,
            output_path=output_path_,
            max_width=cfg.MAX_IMG_WIDTH,
            max_height=cfg.MAX_IMG_HEIGHT,
            thread_count=cfg.MAX_CONCURRENT_REQUEST,
            save_format=cfg.IMG_SAVE_FORMAT,
        )

    def _convert_to_image_and_save(
        self, page_bitmap: PdfBitmap, page_index: int, output_folder: Path
    ) -> tuple[Path, tuple[int, int]]:
        pil_image = page_bitmap.to_pil()

        save_format_ = "PNG" if self.save_format == "png" else self.save_format
        save_path = output_folder / f"Page_{page_index:04}.png"
        if not self.resize_ops_enabled:
            logger.info(
                f"processing Page No {page_index} Images shape {pil_image.size} ..."
            )
            pil_image.save(save_path, save_format_)
        else:
            width, height = pil_image.size
            if width < height and height > self.max_height:
                new_height = self.max_height
                new_width = int(new_height * (width / height))
                new_image = pil_image.resize((new_width, new_height))
                logger.info(
                    f"processing Page No {page_index} Images shape {new_image.size} ..."
                )
                new_image.save(save_path, save_format_)
            elif width > height and width > self.max_width:
                new_width = self.max_width
                new_height = int(new_width * (height / width))
                new_image = pil_image.resize((new_width, new_height))
                logger.info(
                    f"processing Page No {page_index} Images shape {new_image.size} ..."
                )
                new_image.save(save_path, save_format_)
            else:
                logger.info(
                    f"processing Page No {page_index} Images shape {pil_image.size} ..."
                )
                pil_image.save(save_path, save_format_)
        return save_path, pil_image.size

    def _resolve_conflict(self, subfolder: str) -> str:
        if not (self.output_path / Path(subfolder)).exists():
            return subfolder
        count = 0
        while True:
            count += 1
            if not (self.output_path / Path(f"{subfolder}_{count}")).exists():
                return f"{subfolder}_{count}"

    def run(self, pdf_name: str | Path) -> list[tuple[Path, tuple[int, int]]]:
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
        start_time = time.perf_counter()
        page_details = []
        if page_count == 1:
            p_data = self._convert_to_image_and_save(
                pdf_doc[0].render(scale=2, rotation=0), 1, output_folder
            )
        else:
            if self.thread_count in [0, 1, None]:
                for page_index in range(page_count):
                    p_data = self._convert_to_image_and_save(
                        pdf_doc[page_index].render(scale=2, rotation=0),
                        page_index + 1,
                        output_folder,
                    )
                    page_details.append(p_data)
            else:
                with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
                    futures = [
                        executor.submit(
                            self._convert_to_image_and_save,
                            pdf_doc[page_index].render(scale=2, rotation=0),
                            page_index + 1,
                            output_folder,
                        )
                        for page_index in range(page_count)
                    ]
                    for future in futures:
                        page_details.append(future.result())
        pdf_doc.close()
        logger.info(
            f"Time taken to convert {page_count} pages: {time.perf_counter() - start_time:.2f} seconds"
        )
        return page_details
