from awe.settings import settings
from sqlmodel import create_engine
import logging

if settings.db_log_level == "DEBUG":
    logger = logging.getLogger("sqlalchemy.engine")
    logger.setLevel(settings.db_log_level)

engine = create_engine(
    settings.db_connection_string,
    pool_pre_ping=True,
    pool_recycle=280
)

def init_engine():
    engine.dispose(close=False)
