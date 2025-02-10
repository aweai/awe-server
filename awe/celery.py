from awe.settings import settings
from celery import Celery
from celery.signals import setup_logging
import logging

app = Celery(
    'awe_tasks',
    broker=settings.celery_broker_url,
    backend=settings.celery_backend_url,
    task_routes={
        "awe.awe_agent.tasks.llm_task.llm": {"queue": "llm"},
        "awe.awe_agent.tasks.sd_task.sd": {"queue": "sd"},
        'awe.blockchain.solana.tasks.collect_user_fund.collect_user_fund': {"queue": "tx_token_in"},
        'awe.blockchain.solana.tasks.collect_user_fund.collect_user_staking': {"queue": "tx_token_in"},
        'awe.blockchain.solana.tasks.collect_user_fund.collect_game_pool_charge': {"queue": "tx_token_in"},
        'awe.blockchain.solana.tasks.collect_user_fund.collect_agent_creation_staking': {"queue": "tx_token_in"},
        'awe.blockchain.solana.tasks.transfer_to_user.transfer_to_user': {"queue": "tx_token_out"},
        'awe.blockchain.solana.tasks.transfer_to_user.batch_transfer_to_users': {"queue": "tx_token_out"},
    })


@setup_logging.connect
def setup_logging(*args, **kwargs):
    # Disable Celery from hijacking our loggers...

    # Remove httpx logging
    logger = logging.getLogger("httpx")

    if settings.log_level != "DEBUG":
        logger.setLevel("WARN")
