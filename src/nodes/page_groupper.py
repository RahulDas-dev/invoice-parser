import asyncio
import json
from asyncio.log import logger
from typing import Any, Mapping

from pydantic_ai import Agent

from src.config import InvoiceParserConfig
from src.state import TokenCount
from src.utility import (
    extract_json_from_text,
    model_factory,
)

from .messages import PAGE_GROUPPER_SYSTEM_MESSAGE, PAGE_GROUPPER_USER_MESSAGE


class PageGroupper:
    def __init__(self, config: InvoiceParserConfig):
        self.model_name = config.PAGE_GROUPPER_MODEL
        self.semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_REQUEST)

    async def run(self, page_metadata: Mapping[str, Any], page_no: str) -> tuple[Mapping[str, Any], TokenCount | None]:
        """
        Process the image and return a text description.
        """
        agent = Agent[None, str](
            model=model_factory(model_name=self.model_name, provider="openai"),
            system_prompt=PAGE_GROUPPER_SYSTEM_MESSAGE,
            output_type=str,
            retries=0,
            model_settings={"temperature": 1},
        )

        message = PAGE_GROUPPER_USER_MESSAGE.substitute(PAGE_METADATA=str(page_metadata))
        try:
            agent_response = await agent.run(user_prompt=message)
            if agent_response.output in [None, ""]:
                logger.error(f"Page Groupper response is None for page {page_no}")
                return {}, None
            json_string = extract_json_from_text(agent_response.output)
            json_string_ = agent_response.output if json_string is None else json_string
            page_group_info = json.loads(json_string_)
        except Exception as err:
            logger.error(f"Error processing page {page_no}: {err}")
            return {}, None
        token_expenditure = TokenCount(
            model_name=agent.model.model_name,
            page_no=page_no,
            request_tokens=agent_response.usage().request_tokens,
            response_tokens=agent_response.usage().response_tokens,
        )
        return page_group_info, token_expenditure
