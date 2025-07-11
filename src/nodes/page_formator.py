import asyncio
from asyncio.log import logger
from typing import Any

from pydantic_ai import Agent, ModelRetry
from pydantic_ai.agent import AgentRunResult

from src.config import InvoiceParserConfig
from src.output_format import Invoice, TokenCount
from src.utility import model_factory

from .messages import (
    MP_FORMATOR_SYSTEM_MESSAGE,
    MP_FORMATOR_USER_MESSAGE,
    SP_FORMATOR_SYSTEM_MESSAGE,
    SP_FORMATOR_USER_MESSAGE,
)


class SinglePageFormator:
    def __init__(self, config: InvoiceParserConfig):
        self.model_name = config.OUTPUT_FORMATOR_MODEL
        self.semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_REQUEST)

    async def run(
        self, page_details: list[tuple[int, str, dict]]
    ) -> tuple[list[tuple[int, Invoice, TokenCount]], str | None]:
        """
        Process the image and return a text description.
        """
        agent = Agent[None, Invoice](
            model=model_factory(model_name=self.model_name, provider="openai"),
            system_prompt=SP_FORMATOR_SYSTEM_MESSAGE,
            output_type=Invoice,
            retries=5,
            model_settings={"temperature": 0},
        )

        @agent.output_validator
        async def validate_output(result: Any) -> Invoice:
            if isinstance(result, Invoice):
                return result
            raise ModelRetry("Final Result is not valid")

        async def _run_agent(text_content: str, page_no: int) -> tuple[AgentRunResult[Invoice], int]:
            async with self.semaphore:
                input_msg = SP_FORMATOR_USER_MESSAGE.substitute(
                    PAGE_CONTENT=text_content,
                )
                result = await agent.run(user_prompt=input_msg)
                return result, page_no

        task_list = [_run_agent(text_content, page_no) for (page_no, text_content, _) in page_details]
        try:
            agent_response = await asyncio.gather(*task_list)
        except Exception as err:
            logger.error(f"Error in SinglePageFormator Response - {err!s}")
            return [], str(err)
        outputs = []
        for agent_res, page_no in agent_response:
            token_expense = TokenCount(
                model_name=self.model_name,
                page_no=f"P{page_no}",
                request_tokens=agent_res.usage().request_tokens or None,
                response_tokens=agent_res.usage().response_tokens or None,
            )
            outputs.append((page_no, agent_res.output, token_expense))
        return outputs, None


class MultiPageFormator:
    def __init__(self, config: InvoiceParserConfig):
        self.model_name = config.PAGE_GROUPPER_MODEL
        self.semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_REQUEST)

    async def run(self, page_details: list[tuple[str, dict, str]]) -> list[tuple[Invoice, TokenCount]]:
        """
        Process the image and return a text description.
        """
        agent = Agent[None, Invoice](
            model=model_factory(model_name=self.model_name, provider="openai"),
            system_prompt=MP_FORMATOR_SYSTEM_MESSAGE,
            output_type=Invoice,
            retries=0,
            model_settings={"temperature": 0},
        )

        async def run_agent(text_content: str, metadata: dict, page_no: str) -> tuple[AgentRunResult[Invoice], str]:
            async with self.semaphore:
                logger.info(f"Image To Text Converter Agent Processing Page : {page_no} : {text_content}")
                input_msg = MP_FORMATOR_USER_MESSAGE.substitute(
                    PAGE_CONTENT=text_content,
                    PAGE_METADATA=metadata,
                )
                result = await agent.run(user_prompt=input_msg)
                return result, page_no

        task_list = [run_agent(text_content, metadata, page_no) for (text_content, metadata, page_no) in page_details]
        try:
            agent_response = await asyncio.gather(*task_list)
        except Exception as err:
            logger.error(f"Error in MultiPageFormator Response - {err!s}")
            return []
        outputs = []
        for agent_res, page_no in agent_response:
            token_expense = TokenCount(
                model_name=self.model_name,
                page_no=page_no,
                request_tokens=agent_res.usage().request_tokens or None,
                response_tokens=agent_res.usage().response_tokens or None,
            )

            outputs.append((agent_res.output, token_expense))
        return outputs
