from typing import Annotated
from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse, JSONResponse
from awe.blockchain.phantom import decrypt_phantom_data, verify_signature
from sqlmodel import Session, select
from sqlalchemy.orm import load_only
from awe.db import engine
from awe.models.tg_phantom_used_nonce import TGPhantomUsedNonce
from awe.models.tg_bot_user_wallet import TGBotUserWallet
from awe.models.user_agent import UserAgent
import json
import logging
import traceback

logger = logging.getLogger("[Phantom Walllet API]")

router = APIRouter(
    prefix="/v1/tg-phantom-wallets"
)

@router.get("/connect/{agent_id}/{tg_user_id}")
def handle_phantom_connect_callback(
    agent_id: int,
    tg_user_id: str,
    timestamp: int,
    signature: str,
    error_code: Annotated[str | None, Query(alias="errorCode")] = None,
    error_message: Annotated[str | None, Query(alias="errorMessage")] = None,
    phantom_encryption_public_key: str | None = None,
    nonce: str | None = None,
    data: str | None = None
):
    if error_code is not None:
        return {"errorCode": error_code, "errorMessage": error_message}

    if phantom_encryption_public_key is None or phantom_encryption_public_key == "" or nonce is None or nonce == "" or data is None or data == "":
        return {"errorMessage": "Incomplete request from Phantom"}

    # Check signature and timestamp
    err_msg = verify_signature(agent_id, tg_user_id, timestamp, signature)
    if err_msg is not None:
        return {"errorMessage": err_msg}

    # Check if nonce is already used
    # Race condition here
    # Not a big problem since there is only one person having the private key so concurrent requests are rare.
    with Session(engine) as session:
        statement = select(TGPhantomUsedNonce).where(TGPhantomUsedNonce.nonce == nonce)
        used_nonce = session.exec(statement).first()
        if used_nonce is not None:
            return {"errorMessage": "Nonce is already used"}

        used_nonce = TGPhantomUsedNonce(nonce=nonce)
        session.add(used_nonce)
        session.commit()

    # Decrypt the data
    # Public key ownership is not verified here
    try:
        plain_data = decrypt_phantom_data(phantom_encryption_public_key, nonce, data)
        data_dict = json.loads(plain_data)
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())
        return {"errorMessage": "Decryption failed for data returned from Phantom"}

    if 'session' not in data_dict:
        return {"errorMessage": "Invalid request from Phantom"}

    # Save the session and redirect to the TG Miniapp to do the wallet ownership verification
    with Session(engine) as session:
        statement = select(TGBotUserWallet).where(TGBotUserWallet.user_agent_id == agent_id, TGBotUserWallet.tg_user_id == tg_user_id)
        user_wallet = session.exec(statement).first()

        if user_wallet is None:
            user_wallet = TGBotUserWallet(user_agent_id=agent_id, tg_user_id=tg_user_id)

        user_wallet.session = data_dict["session"]
        session.add(user_wallet)
        session.commit()

    # Get TG Bot username for redirection
    with Session(engine) as session:
        statement = select(UserAgent).options(load_only(UserAgent.tg_bot, UserAgent.enabled)).where(UserAgent.id == agent_id)
        user_agent = session.exec(statement).first()

        if user_agent is None or not user_agent.enabled:
            return {"errorMessage": "Agent not found"}

    return {"tg_bot": user_agent.tg_bot.username, "phantom_session": data_dict["session"]}
    # return RedirectResponse(f"https://t.me/{user_agent.tg_bot.username}/awe_tg_miniapp?start=verify_wallet")
