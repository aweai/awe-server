from langchain.tools import BaseTool
from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun
from typing import Optional
from awe.models.tg_bot_user_wallet import TGBotUserWallet
import asyncio
from awe.models.user_agent_data import UserAgentData
from awe.models.awe_agent import AweTokenConfig

class AweTokenTool(BaseTool):

    user_agent_id: int
    awe_token_config: AweTokenConfig

    def get_tg_user_id(self, run_manager: Optional[AsyncCallbackManagerForToolRun]) -> str:
        if run_manager is None or "tg_user_id" not in run_manager.metadata:
            raise Exception("tg_user_id is not set")

        return run_manager.metadata["tg_user_id"]

    async def get_tg_user_address(self, run_manager: Optional[AsyncCallbackManagerForToolRun]) -> str:
        tg_user_id = self.get_tg_user_id(run_manager)
        user_wallet = await asyncio.to_thread(TGBotUserWallet.get_user_wallet, self.user_agent_id, tg_user_id)
        if user_wallet is None or user_wallet.address is None:
            return ""
        return user_wallet.address

    async def get_agent_data(self) -> Optional[UserAgentData]:
        return await asyncio.to_thread(UserAgentData.get_user_agent_data_by_id, self.user_agent_id)
