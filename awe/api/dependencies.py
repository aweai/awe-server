from typing import Annotated
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from awe.blockchain import awe_on_chain
import base64
import json
from time import time
import logging
import traceback
import os
from sqlmodel import Session, select
from awe.db import engine
from awe.models.user_agent import UserAgent
from sqlalchemy import func

logger = logging.getLogger("[API Depends]")

security = HTTPBearer()

def get_admin(credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]) -> str:
    exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    admin_token = os.getenv("ADMIN_TOKEN", "")

    if admin_token == "":
        raise Exception("Admin token is not set")

    if admin_token != credentials.credentials:
        exception.detail = "Admin auth failed"
        raise exception

    return "admin"



def get_current_user(credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]) -> str:

    exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials

    logger.debug(f"Auth API access with token: {token}")

    try:
        b64_decoded = base64.b64decode(token)

        logger.debug(f"Base64 decoded token: {b64_decoded}")

        token_dict = json.loads(b64_decoded)

        logger.debug(f"Token dict: {token_dict}")

    except:
        exception.detail = "Invalid token format"
        raise exception

    # Check timestamp
    if "expires" not in token_dict:
        logger.debug(f"No expires key")
        exception.detail = "No expires key"
        raise exception

    current_timestamp = int(time())
    if token_dict["expires"] <= current_timestamp:
        logger.debug(f"Token expired")
        exception.detail = "Token expired"
        raise exception

    # Check signature
    if "signature" not in token_dict or token_dict["signature"] is None or token_dict["signature"] == "":
        logger.debug(f"No signature key")
        exception.detail = "No signature key"
        raise exception

    if "public_key" not in token_dict or token_dict["public_key"] is None or token_dict["public_key"] == "":
        logger.debug(f"No public_key key")
        exception.detail = "No public_key key"
        raise exception

    message_dict = {
        "expires": token_dict["expires"],
        "public_key": token_dict["public_key"]
    }

    try:
        message_str = json.dumps(message_dict, separators=(',', ':'))
        signature = token_dict["signature"]
        public_key = token_dict["public_key"]

        logger.debug(f"Message string: {message_str}")
        logger.debug(f"Public key: {public_key}")
        logger.debug(f"Signature: {signature}")

        address = awe_on_chain.validate_signature(public_key, message_str, signature)
    except Exception as e:
        print(traceback.format_exc())
        logger.debug(f"Exception in signature validation")
        exception.detail = "Invalid signature"
        raise exception

    if address is None or address == "":
        logger.debug(f"Invalid signature")
        exception.detail = "Invalid signature"
        raise exception

    return address


def validate_user_agent(agent_id, user_address: Annotated[str, Depends(get_current_user)]) -> bool:
    exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid agent id"
    )

    with Session(engine) as session:
        statement = select(func.count(UserAgent.id)).where(UserAgent.id == agent_id, UserAgent.user_address == user_address)
        count = session.exec(statement).one()
        if count == 0:
            raise exception

    return True
