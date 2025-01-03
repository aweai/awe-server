from .awe_token_tool import AweTokenTool
from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun
import asyncio
import logging

from awe.models.user_agent_stats_invocations import UserAgentStatsInvocations, AITools
from awe.agent_manager.agent_fund import transfer_to_user, TransferToUserNotAllowedException

logger = logging.getLogger("[Awe Transfer Tool]")

from typing import Any, Optional

class AweTransferTool(AweTokenTool):
    name: str = "TransferAweToken"
    description: str =  (
        "Useful for when you need to transfer the AWE tokens to user."
        "Input: an integer wrapped as string, no decimal part, representing the amount of tokens you want to transfer to the user."
        "Output: the number of tokens transferred to the user"
    )
    return_direct: bool = True

    async def _arun(self, amount: int = 0, *args: Any, run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:

        tg_user_id = self.get_tg_user_id(run_manager)
        wallet_address = await self.get_tg_user_address(run_manager)

        if wallet_address == "":
            return "You didn't set your Solana wallet address to receive tokens. Please DM me with /wallet command to set your wallet address."

        try:
            tx = await asyncio.to_thread(transfer_to_user, self.user_agent_id, tg_user_id, wallet_address, amount)
        except TransferToUserNotAllowedException as e:
            return str(e)
        except Exception as e:
            logger.error(e)
            return "Something is wrong. Please try again later."

        # Log the invocation
        UserAgentStatsInvocations.add_invocation(self.user_agent_id, tg_user_id, AITools.TOKEN_TRANSFER)

        return f"{amount}.00 AWEs have been transferred to {wallet_address}. The transaction should be confirmed in a short while. \n\n{tx}"

    def _run(self, _: str) -> str:
        raise Exception("Sync call should never be used")
