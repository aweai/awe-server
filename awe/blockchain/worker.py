from awe.settings import settings
from ..celery import app
from .solana.tasks.collect_user_fund import collect_user_fund, collect_user_staking
from .solana.tasks.transfer_to_user import transfer_to_user
