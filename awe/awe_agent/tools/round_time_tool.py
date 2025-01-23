from langchain.tools import BaseTool
import asyncio
import logging
from awe.models import UserAgentData
from awe.models.utils import unix_timestamp_in_seconds
from datetime import datetime
import traceback

logger = logging.getLogger("[SOL Price Tool]")

class RoundTimeTool(BaseTool):
    name: str = "RountTime"
    description: str =  (
        "Get the round start time and current time"
    )

    user_agent_id: int

    def timestamp_to_str(self, timestamp: int) -> str:
        datetime_obj = datetime.fromtimestamp(timestamp)
        return datetime_obj.strftime("%Y-%m-%d %H:%M:%S")

    async def _arun(self) -> str:
        try:
            agent_data = await asyncio.to_thread(UserAgentData.get_user_agent_data_by_id, self.user_agent_id)
        except Exception as e:
            logger.error(e)
            logger.error(traceback.format_exc())

        logger.debug

        round_started_at = self.timestamp_to_str(agent_data.current_round_started_at)
        current_time = self.timestamp_to_str(unix_timestamp_in_seconds())

        return f"Round started at: {round_started_at}. Current time is: {current_time}"

    def _run(self, _: str) -> str:
        raise Exception("Sync call should never be used")
