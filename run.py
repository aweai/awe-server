from awe.settings import settings
from awe.agent_manager.agent_manager import AgentManager
import logging
import uvicorn
from awe.api.app import app
import multiprocessing as mp
from awe.db import init_engine
from awe.cache import init_cache
from awe.payment_processor import PaymentProcessor

def start_payment_processor():
    init_engine()
    init_cache()
    processor = PaymentProcessor()
    processor.start()


def start_api_server():
    init_engine()
    init_cache()
    uvicorn.run(app, host="0.0.0.0", port=7777)


if __name__ == "__main__":

    logger = logging.getLogger("[Main]")

    logger.info("Awe starting...")

    logger.info("Starting API server...")
    api_server = mp.Process(target=start_api_server)
    api_server.daemon = True
    api_server.start()

    logger.info("Starting payment processor...")
    payment_processor = mp.Process(target=start_payment_processor)
    payment_processor.daemon = True
    payment_processor.start()

    logger.info("Starting agent manager...")
    AgentManager().run()

    logger.info("Awe stopped!")
