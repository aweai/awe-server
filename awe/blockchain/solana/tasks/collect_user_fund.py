from ....celery import app
import logging
from solders.pubkey import Pubkey
from solders.transaction import Transaction
from solana.rpc.types import TxOpts
from spl.token.constants import TOKEN_2022_PROGRAM_ID
import spl.token.instructions as spl_token
from .utils import system_payer, awe_mint_public_key, http_client
from awe.settings import settings

logger = logging.getLogger("[Collect User Fund Task]")

@app.task
def collect_user_fund(user_wallet: str, agent_creator_wallet: str, amount: int) -> str:
    # 69% to the pool (system wallet)
    # 30% to the agent creator
    # 1% to the developer

    agent_creator_amount = int(amount * settings.tn_agent_creator_share)
    developer_amount = int(amount * settings.tn_developer_share)
    pool_amount = amount - agent_creator_amount - developer_amount

    logger.info(f"collecting user payment: {user_wallet}: {amount}, agent creator: {agent_creator_wallet}, pool: {pool_amount}, creator: {agent_creator_amount}, developer: {developer_amount}")

    system_payer_associated_token_account = spl_token.get_associated_token_address(
        system_payer.pubkey(),
        awe_mint_public_key,
        TOKEN_2022_PROGRAM_ID
    )

    agent_creator_pub_key = Pubkey.from_string(agent_creator_wallet)
    agent_creator_associated_token_account = spl_token.get_associated_token_address(
        agent_creator_pub_key,
        awe_mint_public_key,
        TOKEN_2022_PROGRAM_ID
    )

    developer_pub_key = Pubkey.from_string(settings.solana_developer_wallet)
    developer_associated_token_account = spl_token.get_associated_token_address(
        developer_pub_key,
        awe_mint_public_key,
        TOKEN_2022_PROGRAM_ID
    )

    user_wallet_pk = Pubkey.from_string(user_wallet)
    user_associated_token_account = spl_token.get_associated_token_address(
        user_wallet_pk,
        awe_mint_public_key,
        TOKEN_2022_PROGRAM_ID
    )

    logger.debug(f"source: {str(user_associated_token_account)}, system: {str(system_payer_associated_token_account)}, agent creator: {str(agent_creator_associated_token_account)}")
    logger.debug(f"signer: {str(system_payer.pubkey())}")

    # 69% to the pool
    ix_user = spl_token.transfer_checked(spl_token.TransferCheckedParams(
        source=user_associated_token_account,
        dest=system_payer_associated_token_account,
        owner=system_payer.pubkey(),
        amount=int(pool_amount * 1e9),
        decimals=9,
        mint=awe_mint_public_key,
        program_id=TOKEN_2022_PROGRAM_ID
    ))

    # 30% to the agent creator
    ix_agent_creator = spl_token.transfer_checked(spl_token.TransferCheckedParams(
        source=user_associated_token_account,
        dest=agent_creator_associated_token_account,
        owner=system_payer.pubkey(),
        amount=int(agent_creator_amount * 1e9),
        decimals=9,
        mint=awe_mint_public_key,
        program_id=TOKEN_2022_PROGRAM_ID
    ))

    # %1 to the developer
    ix_developer = spl_token.transfer_checked(spl_token.TransferCheckedParams(
        source=user_associated_token_account,
        dest=developer_associated_token_account,
        owner=system_payer.pubkey(),
        amount=int(developer_amount * 1e9),
        decimals=9,
        mint=awe_mint_public_key,
        program_id=TOKEN_2022_PROGRAM_ID
    ))

    recent_blockhash = http_client.get_latest_blockhash().value.blockhash

    tx = Transaction.new_signed_with_payer(
        [ix_user, ix_agent_creator, ix_developer],
        system_payer.pubkey(),
        [system_payer],
        recent_blockhash
    )

    send_tx_resp = http_client.send_transaction(tx, TxOpts(skip_confirmation=False))
    return str(send_tx_resp.value)
