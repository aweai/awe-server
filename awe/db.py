from sqlmodel import create_engine
import os
import logging

logger = logging.getLogger("sqlalchemy.engine")
log_level = os.getenv("LOG_LEVEL", logging.INFO)
logger.setLevel(log_level)

db_connection_str = os.getenv("DB_CONNECTION_STRING", "")

if db_connection_str == "":
    raise Exception("DB_CONNECTION_STRING is not specified!")

engine = create_engine(db_connection_str)
