import asyncio
from typing import Any
from .awe_token_tool import AweTokenTool
import logging
from awe.models.user_agent_stats_invocations import UserAgentStatsInvocations, AITools
from langchain_core.runnables.config import RunnableConfig

logger = logging.getLogger("[AweBalanceTool]")

class AweAgentBalanceTool(AweTokenTool):
    name: str = "MyOwnBalance"
    description: str =  (
        "Useful for when you need to check how many tokens you have."
    )

    async def _arun(self, config: RunnableConfig) -> str:

        tg_user_id = config.get("configurable", {}).get("tg_user_id")

        agent_data = await self.get_agent_data()
        await asyncio.to_thread(UserAgentStatsInvocations.add_invocation, self.user_agent_id, tg_user_id, AITools.AGENT_POOL_QUERY)

        return f"AWE {agent_data.awe_token_quote}.00"

    def _run(self, _: str) -> str:
        raise Exception("Sync call should never be used")
