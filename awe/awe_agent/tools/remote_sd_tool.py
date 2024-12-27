from typing import Optional
from langchain.tools import BaseTool
from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun
from pathlib import Path
from datetime import datetime
import uuid
import asyncio
from ...celery import app
import logging
from io import BytesIO
from PIL import Image
import base64
import random
import logging
from awe.settings import settings
from awe.models.user_agent_stats_invocations import UserAgentStatsInvocations, AITools

logger = logging.getLogger("[Remote SD Tool]")

class RemoteSDTool(BaseTool):
    name: str = "GenerateImage"
    description: str =  (
        "Useful for when you need to generate an image using text prompt."
        "Input: A string as detailed text-2-image prompt describing the image. The string should be created from the user input, should be as detailed as possible, every element in the image, the shape, color, position of the element, the background."
        "Output: the base64 encoded string of the image"
    )
    return_direct: bool = True

    task_args: dict

    user_agent_id: int

    def run_until_complete(self, tg_user_id: str, prompt: str) -> str:

        self.task_args["prompt"] = prompt
        self.task_args["task_config"]["seed"] = random.randint(10000000, 99999999)

        task = app.send_task(name="awe.awe_agent.tasks.sd_task.sd", args=(self.task_args,), countdown=5, expires=60)
        logger.info("Sent SD task to the queue")

        # Log the invocation
        UserAgentStatsInvocations.add_invocation(self.user_agent_id, tg_user_id, AITools.SD)

        resp = ""

        try:
            resp = task.get(timeout=settings.sd_task_timeout)
        except Exception as e:
            logger.error(e)

        return resp

    def write_image_to_file(self, image_b64:str) -> str:
        image_bytes = base64.b64decode(image_b64.encode("utf-8"))
        image = Image.open(BytesIO(image_bytes))

        image_path = Path("persisted_data") / "images" / datetime.today().strftime('%Y-%m-%d')
        image_path.mkdir(parents=True, exist_ok=True)

        image_id = uuid.uuid4()
        image_filename = image_path / f"{image_id}.jpg"

        image.save(image_filename)

        return image_filename

    async def _arun(self, prompt: str = None, run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:

        if run_manager is None or "tg_user_id" not in run_manager.metadata:
            raise Exception("tg_user_id is not set")

        tg_user_id = run_manager.metadata["tg_user_id"]

        if prompt is None or prompt == "":
            return ""

        image_b64 = await asyncio.to_thread(self.run_until_complete, tg_user_id, prompt)
        if image_b64 == "":
            return ""
        image_filename = await asyncio.to_thread(self.write_image_to_file, image_b64)
        return f"[image]{image_filename}"

    def _run(self, _: str) -> str:
        raise Exception("Sync call should never be used")
