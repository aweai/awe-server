import asyncio
from awe.blockchain import awe_on_chain
from typing import Any, Optional
from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun
from .awe_token_tool import AweTokenTool
import logging
from awe.models.user_agent_stats_invocations import UserAgentStatsInvocations, AITools

logger = logging.getLogger("[AweBalanceTool]")

class AweBalanceTool(AweTokenTool):
    name: str = "QueryAweBalance"
    description: str =  (
        "Useful for when you need to check the balance of the user, not yourself."
        "Input: an empty string, no other info needed"
        "Output: the balance of the AWE token in the wallet"
    )
    return_direct: bool = True

    def run_until_complete(self, tg_user_id: str, address: str) -> str:
        balance = awe_on_chain.get_balance(address)

        # Log the invocation
        UserAgentStatsInvocations.add_invocation(self.user_agent_id, tg_user_id, AITools.TOKEN_QUERY)

        return awe_on_chain.token_ui_amount(balance)

    async def _arun(self, *args: Any, run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:

        tg_user_id = self.get_tg_user_id(run_manager)
        wallet_address = await self.get_tg_user_address(run_manager)

        if wallet_address == "":
            return "You didn't set your Solana wallet address to receive tokens. Please DM me with /wallet {address} command to set your wallet address."

        awe_balance_ui = await asyncio.to_thread(self.run_until_complete, tg_user_id, wallet_address)

        return f"{awe_balance_ui}"

    def _run(self, _: str) -> str:
        raise Exception("Sync call should never be used")
