from .awe_token_tool import AweTokenTool
from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun
import asyncio
from awe.blockchain import awe_on_chain
import logging
from awe.models.user_agent_stats_token_transfers import UserAgentStatsTokenTransfers
from awe.models.user_agent_stats_invocations import UserAgentStatsInvocations, AITools

logger = logging.getLogger("[Awe Transfer Tool]")

from typing import Any, Optional

class AweTransferTool(AweTokenTool):
    name: str = "TransferAweToken"
    description: str =  (
        "Useful for when you need to transfer the AWE tokens to user."
        "Input: an integer representing the amount of tokens you want to transfer to the user."
        "Output: the number of tokens transferred to the user"
    )
    return_direct: bool = True

    def run_until_complete(self, tg_user_id: str, address: str, amount: int) -> str:
        amount = int(amount)
        amount_full = int(int(amount) * int(1e9))
        awe_on_chain.transfer_token(address, amount_full)

        # Log the transfer
        UserAgentStatsTokenTransfers.add_invocation(self.user_agent_id, tg_user_id, address, amount)

        # Log the invocation
        UserAgentStatsInvocations.add_invocation(self.user_agent_id, tg_user_id, AITools.TOKEN_TRANSFER)

        return f"{awe_on_chain.token_ui_amount(amount_full)} have been transferred to {address}. The transaction should be confirmed in a short while."

    async def _arun(self, amount: int = 0, *args: Any, run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:

        amount = int(amount)

        logger.info(f"Transferring {amount} tokens")

        if amount > self.awe_token_config.max_token_per_tx:
            return "Token amount exceeds the maximum allowed!"

        user_agent_data = await self.get_agent_data()

        if user_agent_data is None:
            logger.warning(f"user_agent_data not found for agent {self.user_agent_id}")
            return "No token to transfer!"

        if amount + user_agent_data.awe_token_round_transferred > self.awe_token_config.max_token_per_round or user_agent_data.awe_token_quote < amount:
            return "Token amount exceeds the maximum allowed!"

        tg_user_id = self.get_tg_user_id(run_manager)
        wallet_address = await self.get_tg_user_address(run_manager)

        if wallet_address == "":
            return "You didn't set your Solana wallet address to receive tokens. Please DM me with /wallet {address} command to set your wallet address."

        awe_balance_ui = await asyncio.to_thread(self.run_until_complete, tg_user_id, wallet_address, amount)

        await self.add_agent_round_transferred_awe(amount)

        return f"{awe_balance_ui}"

    def _run(self, _: str) -> str:
        raise Exception("Sync call should never be used")
