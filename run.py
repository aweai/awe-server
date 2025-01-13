from awe.settings import settings
from awe.agent_manager.agent_manager import AgentManager
import logging
import uvicorn
from awe.api.app import app
import multiprocessing as mp

def start_api_server():
    uvicorn.run(app, host="0.0.0.0", port=7777)

if __name__ == "__main__":

    mp.set_start_method('spawn')

    logger = logging.getLogger("[Main]")

    logger.info("Awe starting...")

    logger.info("Starting API server...")
    api_server = mp.Process(target=start_api_server)
    api_server.daemon = True
    api_server.start()

    logger.info("Starting agent manager...")
    AgentManager().run()

    logger.info("Awe stopped!")
