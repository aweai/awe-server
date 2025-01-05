import asyncio
from typing import Any, Optional
from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun
from .awe_token_tool import AweTokenTool
import logging
from awe.models.user_agent_stats_invocations import UserAgentStatsInvocations, AITools

logger = logging.getLogger("[AweBalanceTool]")

class AweAgentBalanceTool(AweTokenTool):
    name: str = "MyOwnBalance"
    description: str =  (
        "Useful for when you need to check how many tokens you have."
        "Input: an empty string, no other info needed"
        "Output: the balance of yourself"
    )
    return_direct: bool = True

    async def _arun(self, *args: Any, run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:

        tg_user_id = self.get_tg_user_id(run_manager)

        agent_data = await self.get_agent_data()
        await asyncio.to_thread(UserAgentStatsInvocations.add_invocation, self.user_agent_id, tg_user_id, AITools.AGENT_POOL_QUERY)

        return f"{agent_data.awe_token_quote}"

    def _run(self, _: str) -> str:
        raise Exception("Sync call should never be used")
