import asyncio
import logging
from pathlib import Path

from pydantic_ai import Agent, BinaryContent
from pydantic_ai.agent import AgentRunResult

from src.config import InvoiceParserConfig
from src.output_format import TokenCount
from src.utility import (
    extract_invoice_metadata,
    extract_json_from_text,
    image_to_byte_string,
    model_factory,
    replace_json_from_text,
    sorted_images,
)

from .messages import (
    IMAGE_TO_TEXT_SYSTEM_MESSAGE,
    IMAGE_TO_TEXT_USER_MESSAGE,
)

logger = logging.getLogger("asyncio")


class ImageToTextConverter:
    def __init__(self, config: InvoiceParserConfig):
        self.model_name = config.IMAGE_TO_TEXT_MODEL
        self.semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_REQUEST)
        self.image_ext = config.IMG_SAVE_FORMAT

    async def run(self, image_dir: Path | str) -> tuple[list[tuple[int, str, dict, TokenCount]], str | None]:
        """
        Process the image and return a text description.
        """
        agent = Agent(
            model=model_factory(model_name=self.model_name, provider="aws_bedrock"),
            system_prompt=IMAGE_TO_TEXT_SYSTEM_MESSAGE,
            output_type=str,
            retries=1,
            model_settings={"temperature": 0},
        )

        async def _run_agent(image_path: Path, page_no: int) -> tuple[AgentRunResult[str], Path, int]:
            async with self.semaphore:
                logger.info(f"Image To Text Converter Agent Processing Page : {page_no} : {image_path.name}")
                img_byte, mimetype = image_to_byte_string(image_path.resolve())
                input_msg = [
                    IMAGE_TO_TEXT_USER_MESSAGE,
                    BinaryContent(data=img_byte, media_type=mimetype),
                ]
                result = await agent.run(user_prompt=input_msg)
                return result, image_path, page_no

        task_list = [
            _run_agent(img_path, page_no)
            async for img_path, page_no in sorted_images(image_dir, image_ext=self.image_ext)
        ]
        try:
            agent_response = await asyncio.gather(*task_list)
        except Exception as err:
            logger.error(f"Error in Image To Text Converter Agent Response - {err!s}")
            return [], str(err)
        outputs = []
        for agent_res, _, page_no in agent_response:
            json_string = extract_json_from_text(agent_res.output)
            page_metadata = extract_invoice_metadata(json_string) if json_string is not None else {}
            text_content = replace_json_from_text(agent_res.output)
            logger.info(f"Extracted Metadata for Page {page_no}: {page_metadata}")
            logger.info(f"Extracted Text for Page {page_no}: {text_content[:100]} ...")
            token_expense = TokenCount(
                model_name=self.model_name,
                page_no=str(page_no),
                request_tokens=agent_res.usage().request_tokens or None,
                response_tokens=agent_res.usage().response_tokens or None,
            )
            outputs.append((page_no, text_content, page_metadata, token_expense))
        return outputs, None
