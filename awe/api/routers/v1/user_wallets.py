import logging
from fastapi import APIRouter, HTTPException, status, Query, BackgroundTasks
from awe.blockchain.phantom import verify_comm_signature, verify_solana_signature
from solders.pubkey import Pubkey
from sqlmodel import Session, select
from awe.db import engine
from awe.models import TGBotUserWallet

logger = logging.getLogger("[Wallet API]")

router = APIRouter(
    prefix="/v1/user-wallets"
)

@router.post("/bind/{agent_id}/{tg_user_id}")
def handle_bind_wallet(agent_id: int, tg_user_id: str, wallet_address: str, timestamp: int, wallet_signature: str, comm_signature: str):

    # Verify comm signature to make sure the request is indeed from the tg_user_id in TG
    err_msg = verify_comm_signature(f"{agent_id}{tg_user_id}{timestamp}", timestamp, comm_signature)
    if err_msg is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err_msg,
        )

    # Verify the wallet signature
    try:
        user_pk = Pubkey.from_string(wallet_address)
    except:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid wallet address",
        )

    err_msg = verify_solana_signature(f"{timestamp}", user_pk, wallet_signature)

    if err_msg is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err_msg,
        )

    # Save the user wallet address
    with Session(engine) as session:
        statement = select(TGBotUserWallet).where(TGBotUserWallet.user_agent_id == agent_id, TGBotUserWallet.tg_user_id == tg_user_id)
        user_wallet = session.exec(statement).first()
        if user_wallet is None:
            user_wallet = TGBotUserWallet(user_agent_id=agent_id, tg_user_id=tg_user_id)

        user_wallet.address = wallet_address

        # This is from the browser wallets
        # Clear the phantom mobile wallet session
        user_wallet.phantom_encryption_public_key = ""
        user_wallet.phantom_session = ""

        session.add(user_wallet)
        session.commit()


@router.post("/approve/{agent_id}/{tg_user_id}/{wallet_address}")
def handle_approve():
    pass
