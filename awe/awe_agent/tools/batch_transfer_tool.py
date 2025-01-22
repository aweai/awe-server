from .awe_token_tool import AweTokenTool
import asyncio
import logging

from awe.models.user_agent_stats_invocations import UserAgentStatsInvocations, AITools
from awe.agent_manager.agent_fund import batch_transfer_to_users, TransferToUserNotAllowedException
from pydantic import BaseModel, Field
from typing import Type, Annotated, List


logger = logging.getLogger("[Awe Batch Transfer Tool]")


class BatchAweTransferInput(BaseModel):
    user_ids: Annotated[List[str], Field(description="the list of user id to transfer")]
    amounts: Annotated[List[int], Field(description="the list of amount of tokens to transfer")]


class BatchAweTransferTool(AweTokenTool):
    name: str = "BatchTransferAweToken"
    description: str =  (
        "Transfer the AWE tokens to a list of selected players in a group chat"
    )

    args_schema: Type[BaseModel] = BatchAweTransferInput

    async def _arun(self, user_ids: List[str], amounts: List[int]) -> str:

        if len(user_ids) == 0 or len(amounts) == 0 or len(user_ids) != len(amounts):
            raise Exception("Invalid user_ids or amounts provided")

        reply_message = "$AWE transferred to:\n\n"

        user_ids_checked = []
        wallet_addresses = []
        wallet_amounts = []

        for idx, user_id in enumerate(user_ids):
            wallet_address = await self.get_tg_user_address_from_id(user_id)
            if wallet_address == "":
                reply_message += f"{user_id}: No wallet address\n"
            else:
                reply_message += f"{wallet_address}: {amounts[idx]}\n"
                user_ids_checked.append(user_id)
                wallet_addresses.append(wallet_address)

                try:
                    amount = int(amounts[idx])
                except:
                    return f"Invalid amount provided for user id {user_id}: {amounts[idx]}"

                wallet_amounts.append(amount)

        try:
            tx = await asyncio.to_thread(batch_transfer_to_users, self.user_agent_id, user_ids_checked, wallet_addresses, wallet_amounts)
        except TransferToUserNotAllowedException as e:
            return str(e)
        except Exception as e:
            logger.error(e)
            return "Something is wrong. Please try again later."

        # Log the invocation
        for user_id in user_ids_checked:
            await asyncio.to_thread(UserAgentStatsInvocations.add_invocation, self.user_agent_id, user_id, AITools.TOKEN_TRANSFER)

        return f"{reply_message}\nThe transaction should be confirmed in a short while. \n\n{tx}"

    def _run(self, _: str) -> str:
        raise Exception("Sync call should never be used")
