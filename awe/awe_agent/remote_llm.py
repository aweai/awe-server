from langchain.llms.base import LLM
from langchain.callbacks.manager import CallbackManagerForLLMRun
from typing import Optional, List, Mapping, Any
import asyncio
import logging
from ..models.awe_agent import LLMConfig
from ..celery import app
from awe.settings import settings

logger = logging.getLogger("[Remote LLM]")

class RemoteLLM(LLM):

    llm_config: LLMConfig

    @property
    def _llm_type(self) -> str:
        return "remote"

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        return {"model": "remote"}

    def run_until_complete(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        task = app.send_task(name='awe.awe_agent.tasks.llm_task.llm', args=(self.llm_config.model_dump(), prompt, stop), countdown=5, expires=60)
        logger.info("Sent remote llm task to the queue")

        resp = ""

        try:
            resp = task.get(timeout=settings.llm_task_timeout)
        except Exception as e:
            logger.error(e)
            raise e

        return resp

    async def _acall(
            self,
            prompt: str,
            stop: Optional[List[str]] = None
    ) -> str:
        resp = await asyncio.to_thread(self.run_until_complete, prompt, stop)
        return resp

    def _call(
            self,
            prompt: str,
            stop: Optional[List[str]] = None,
            _: Optional[CallbackManagerForLLMRun] = None
    ) -> str:
        raise Exception("Sync call should never be used")
