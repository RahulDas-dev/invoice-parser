import asyncio
from asyncio.log import logger
from pathlib import Path

from pydantic_ai import Agent, BinaryContent
from state import TokenCount
from utility import (
    extract_invoice_metadata,
    extract_json_from_text,
    image_to_byte_string,
    model_factory,
    replace_json_from_text,
    sorted_images,
)
from .messages import (
    IMAGE_TO_TEXT_PAGE_TEMPLATE,
    IMAGE_TO_TEXT_SYSTEM_MESSAGE,
    IMAGE_TO_TEXT_USER_MESSAGE,
)
from config import InvoiceParserConfig


class ImageToTextConverter:
    def __init__(self, config: InvoiceParserConfig):
        self.config = config
        self.semaphore = asyncio.Semaphore(config.max_concurrent_request)

    async def run(self, image_path: Path) -> list[tuple[int, str, dict, TokenCount]]:
        """
        Process the image and return a text description.
        """
        agent = Agent(
            model=model_factory(
                model_name=self.config.model1_name, provider="aws_bedrock"
            ),
            system_prompt=IMAGE_TO_TEXT_SYSTEM_MESSAGE,
            output_type=str,
            retries=0,
            model_settings={"temperature": 0},
        )

        async def run_agent(image_path: Path, page_no: int):
            async with self.semaphore:
                logger.info(
                    f"Image To Text Converter Agent Processing Page : {page_no} : {image_path.name}"
                )
                img_byte, mimetype = image_to_byte_string(image_path.resolve())
                input_msg = [
                    IMAGE_TO_TEXT_USER_MESSAGE,
                    BinaryContent(data=img_byte, media_type=mimetype),
                ]
                result = await agent.run(user_prompt=input_msg)
                return result, image_path, page_no

        task_list = [
            run_agent(img_path, page_no)
            for img_path, page_no in sorted_images(
                image_path, image_ext=self.config.image_ext
            )
        ]
        try:
            agent_response = await asyncio.gather(*task_list)
        except Exception as err:
            logger.error(f"Error in Image To Text Converter Agent Response - {err!s}")
            return None
        outputs = []
        for agent_res, image_path, page_no in agent_response:
            json_string = extract_json_from_text(agent_res.output)
            page_metadata = (
                extract_invoice_metadata(json_string) if json_string is not None else {}
            )
            text_content = replace_json_from_text(agent_res.output)
            token_expense = TokenCount(
                model_name=self.config.model1_name,
                page_no=page_no,
                request_tokens=agent_res.usage().request_tokens,
                response_tokens=agent_res.usage().response_tokens,
            )
            page_content = IMAGE_TO_TEXT_PAGE_TEMPLATE.substitute(
                PAGE_NO=page_no,
                PAGE_CONTENT=text_content,
            )
            outputs.append((page_no, page_content, page_metadata, token_expense))
        return outputs
