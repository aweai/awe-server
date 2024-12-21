from dotenv import load_dotenv
load_dotenv("persisted_data/.env")

from awe.agent_manager.agent_manager import AgentManager
import logging
import os
import uvicorn
from awe.api.app import app
import multiprocessing as mp

log_level = os.getenv("LOG_LEVEL", logging.INFO)
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

logging.basicConfig(
    format=log_format,
    level=log_level
)

def start_api_server():
    uvicorn.run(app, host="0.0.0.0", port=7777)

if __name__ == "__main__":

    logger = logging.getLogger("[Main]")

    logger.info("Awe starting...")

    logger.info("Starting API server...")
    api_server = mp.Process(target=start_api_server)
    api_server.daemon = True
    api_server.start()

    logger.info("Starting agent manager...")
    AgentManager().run()

    logger.info("Awe stopped!")
