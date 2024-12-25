from typing import Annotated
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from awe.blockchain.phantom import decrypt_phantom_data, verify_signature
from sqlmodel import Session, select
from sqlalchemy.orm import load_only
from awe.db import engine
from awe.models.tg_phantom_used_nonce import TGPhantomUsedNonce
from awe.models.tg_bot_user_wallet import TGBotUserWallet
from awe.blockchain.phantom import get_wallet_verification_url
from awe.models.user_agent import UserAgent
import json
import logging
import traceback

logger = logging.getLogger("[Phantom Walllet API]")

router = APIRouter(
    prefix="/v1/tg-phantom-wallets"
)

notify_html_template = """
<!DOCTYPE html>
<html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Awe - House of Memegents</title>
        <style>
            html, body {
                position: relative;
                display: block;
                margin: 0;
                padding: 0;
                background-color: #0e0e16;
                font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", "Noto Sans", "Liberation Sans", Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji";
            }
            .logo {
                color: white;
                font-size: 64px;
                font-weight: 800;
                text-align: center;
                margin-top: 120px;
            }
            .logo .w {
                color: #45f882;
            }
            .content {
                position: relative;
                width: 90%;
                margin: 40px auto;
                background-color: white;
                border-radius: 10px;
                overflow: hidden;
                padding: 5%;
                box-sizing: border-box;
                text-align: center;
            }
            .content .message {
                font-size: 30px;
            }

            .content .jump {
                font-size: 16px;
                color: #666;
                margin-top: 64px;
            }
        </style>
    </head>
    <body>
        <div class="logo">A<span class="w">W</span>E</div>
        <div class="content">
            <div class="message">__MESSAGE__</div>
            <div class="jump">Automatically jump back to __DEST_NAME__ in a short while...</div>
        </div>
        <script type="text/javascript">
            setTimeout(function(){
                window.location = '__REDIRECT_LINK__';
            }, 5000)
        </script>
    </body>
</html>
"""

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
    err_msg = verify_signature(f"{agent_id}{tg_user_id}{timestamp}", timestamp, signature)
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

    if 'session' not in data_dict or "public_key" not in data_dict:
        return {"errorMessage": "Invalid request from Phantom"}

    # Save the session and phantom_encryption_public_key for future requests
    with Session(engine) as session:
        statement = select(TGBotUserWallet).where(TGBotUserWallet.user_agent_id == agent_id, TGBotUserWallet.tg_user_id == tg_user_id)
        user_wallet = session.exec(statement).first()

        if user_wallet is None:
            user_wallet = TGBotUserWallet(user_agent_id=agent_id, tg_user_id=tg_user_id)

        user_wallet.phantom_session = data_dict["session"]
        user_wallet.phantom_encryption_public_key = phantom_encryption_public_key
        session.add(user_wallet)
        session.commit()

    # Redirect to Phantom again for wallet address verification
    url = get_wallet_verification_url(
        agent_id,
        tg_user_id,
        data_dict["public_key"],
        data_dict["session"],
        phantom_encryption_public_key
    )

    logger.debug(f"Phantom verification url: {url}")

    # Display success message and redirect back to TG
    html = notify_html_template.replace("__MESSAGE__", "One more step.<br/>We still need to verify your ownership of the wallet.")
    html = html.replace("__REDIRECT_LINK__", url)
    html = html.replace("__DEST_NAME__", "Phantom")
    return HTMLResponse(html)


@router.get("/verify/{agent_id}/{tg_user_id}")
def handle_phantom_verify_callback(
    agent_id: int,
    tg_user_id: str,
    wallet: str,
    timestamp: int,
    signature: str,
    error_code: Annotated[str | None, Query(alias="errorCode")] = None,
    error_message: Annotated[str | None, Query(alias="errorMessage")] = None,
    nonce: str | None = None,
    data: str | None = None
):
    if error_code is not None:
        return {"errorCode": error_code, "errorMessage": error_message}

    # Check signature and timestamp
    err_msg = verify_signature(f"{agent_id}{tg_user_id}{wallet}{timestamp}", timestamp, signature)
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

    # Get phantom_encryption_public_key from database
    with Session(engine) as session:
        statement = select(TGBotUserWallet).where(TGBotUserWallet.user_agent_id == agent_id, TGBotUserWallet.tg_user_id == tg_user_id)
        user_wallet = session.exec(statement).first()
        if user_wallet is None:
            return {"errorMessage": "User wallet not found"}

    if user_wallet.phantom_encryption_public_key is None or user_wallet.phantom_encryption_public_key == "":
        return {"errorMessage": "phantom_encryption_public_key not found"}

    # Decrypt the payload
    try:
        decrypted_payload = decrypt_phantom_data(user_wallet.phantom_encryption_public_key, nonce, data)
        decrypted_payload_dict = json.loads(decrypted_payload)
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())
        return {"errorMessage": "Decryption failed for data returned from Phantom"}

    if 'signature' not in decrypted_payload_dict:
        return {"errorMessage": "Invalid response from Phantom"}

    err_message = verify_signature(f"{timestamp}", timestamp, decrypted_payload_dict["signature"])
    if err_message is not None:
        return {"errorMessage": "Invalid signature from Phantom payload"}

    # Now the ownership of the wallet is verified. Save the wallet address in DB
    with Session(engine) as session:
        statement = select(TGBotUserWallet).where(TGBotUserWallet.user_agent_id == agent_id, TGBotUserWallet.tg_user_id == tg_user_id)
        user_wallet = session.exec(statement).first()
        user_wallet.address = wallet
        session.add(user_wallet)
        session.commit()

    # Get the TG Bot username to jump back
    with Session(engine) as session:
        statement = select(UserAgent).options(load_only(UserAgent.tg_bot)).where(UserAgent.id == agent_id)
        user_agent = session.exec(statement).first()
        if user_agent is None or user_agent.tg_bot is None or user_agent.tg_bot.username == "":
            return {"errorMessage": "Invalid agent"}

    # Display success message and redirect back to TG
    html = notify_html_template.replace("__MESSAGE__", "Your wallet has been bound successfully!")
    html = html.replace("__REDIRECT_LINK__", f"https://t.me/{user_agent.tg_bot.username}")
    html = html.replace("__DEST_NAME__", "Telegram")
    return HTMLResponse(html)
