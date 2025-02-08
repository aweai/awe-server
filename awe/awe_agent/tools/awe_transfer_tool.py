from .awe_token_tool import AweTokenTool
from langchain_core.runnables.config import RunnableConfig
import asyncio
import logging

from awe.models.user_agent_stats_invocations import UserAgentStatsInvocations, AITools
from awe.models import UserAgent, UserAgentData, TgUserAccount
from pydantic import BaseModel, Field
from typing import Type, Dict
from threading import Lock
from awe.db import engine
from sqlmodel import Session, select
from sqlalchemy.orm import joinedload
from awe.agent_manager.agent_stats import record_user_reward


logger = logging.getLogger("[Awe Transfer Tool]")
agent_locks: Dict[int, Lock] = {}


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

        try:
            msg = await asyncio.to_thread(self.transfer_to_user_account, amount, tg_user_id)
        except Exception as e:
            logger.error(e)
            return "Something is wrong. Please try again later."

         # Log the invocation
        await asyncio.to_thread(UserAgentStatsInvocations.add_invocation, self.user_agent_id, tg_user_id, AITools.TOKEN_TRANSFER)

        return msg


    def transfer_to_user_account(self, amount: int, tg_user_id: str) -> str:
        # Lock the agent to prevent race condition
        if self.user_agent_id not in agent_locks:
            agent_locks[self.user_agent_id] = Lock()

        with agent_locks[self.user_agent_id]:
            with Session(engine) as session:
                statement = select(UserAgent).options(joinedload(UserAgent.agent_data)).where(UserAgent.id == self.user_agent_id)
                user_agent = session.exec(statement).first()

                if amount > user_agent.awe_agent.awe_token_config.max_token_per_tx:
                    raise "Token amount exceeds the maximum allowed!"

                if amount + user_agent.agent_data.awe_token_round_transferred > user_agent.awe_agent.awe_token_config.max_token_per_round or user_agent.agent_data.awe_token_quote < amount:
                    raise "Token amount exceeds the maximum allowed!"

                # 1. Decrease game pool
                user_agent.agent_data.awe_token_quote = UserAgentData.awe_token_quote - amount

                # 2. Update round data
                user_agent.agent_data.awe_token_round_transferred = UserAgentData.awe_token_round_transferred + amount

                session.add(user_agent.agent_data)

                # 3. Increase user account balance
                statement = select(TgUserAccount).where(TgUserAccount.tg_user_id == tg_user_id)
                tg_user_account = session.exec(statement).first()

                tg_user_account.balance = TgUserAccount.balance + amount

                session.add(tg_user_account)

                # 4. Record stats
                record_user_reward(self.user_agent_id, amount, session)

                session.commit()

                return f"$AWE {amount}.00 has been successfully transferred to your Awe! account."


    def _run(self, _: str) -> str:
        raise Exception("Sync call should never be used")
