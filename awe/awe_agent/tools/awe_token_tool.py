from langchain.tools import BaseTool
from typing import Optional
from awe.models.tg_bot_user_wallet import TGBotUserWallet
import asyncio
from awe.models.user_agent_data import UserAgentData
from awe.models.awe_agent import AweTokenConfig
from langchain_core.runnables.config import RunnableConfig

class AweTokenTool(BaseTool):

    user_agent_id: int
    awe_token_config: AweTokenConfig

    async def get_tg_user_address_from_id(self, tg_user_id: str) -> str:
        user_wallet = await asyncio.to_thread(TGBotUserWallet.get_user_wallet, self.user_agent_id, tg_user_id)
        if user_wallet is None or user_wallet.address is None:
            return ""

        return user_wallet.address

    async def get_tg_user_address(self, config: RunnableConfig) -> str:
        tg_user_id = config.get("configurable", {}).get("tg_user_id")
        if tg_user_id is None:
            return ""
        return await self.get_tg_user_address_from_id(tg_user_id)

    async def get_agent_data(self) -> Optional[UserAgentData]:
        return await asyncio.to_thread(UserAgentData.get_user_agent_data_by_id, self.user_agent_id)
