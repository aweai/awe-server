from .awe_token_tool import AweTokenTool
from langchain_core.runnables.config import RunnableConfig
import asyncio
import logging

from awe.models.user_agent_stats_invocations import UserAgentStatsInvocations, AITools
from awe.agent_manager.agent_fund import transfer_to_user, TransferToUserNotAllowedException
from pydantic import BaseModel, Field
from typing import Type


logger = logging.getLogger("[Awe Transfer Tool]")


class AweTransferInput(BaseModel):
    amount: str = Field(description="the amount of tokens to transfer")


class AweTransferTool(AweTokenTool):
    name: str = "SingleTransferAweToken"
    description: str =  (
        "Transfer the AWE tokens to the current player in private chat"
    )

    args_schema: Type[BaseModel] = AweTransferInput

    async def _arun(self, amount: int, config: RunnableConfig) -> str:

        tg_user_id = config.get("configurable", {}).get("tg_user_id")

        wallet_address = await self.get_tg_user_address(config)

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
