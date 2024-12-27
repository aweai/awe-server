from awe.settings import settings
from sqlmodel import create_engine
import logging

logger = logging.getLogger("sqlalchemy.engine")
logger.setLevel(settings.log_level)

engine = create_engine(settings.db_connection_string)
