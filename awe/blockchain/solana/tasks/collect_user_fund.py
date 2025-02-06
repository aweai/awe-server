from ....celery import app
import logging
from solders.pubkey import Pubkey
from solders.transaction import Transaction
from solana.rpc.types import TxOpts
from spl.token.constants import TOKEN_2022_PROGRAM_ID
import spl.token.instructions as spl_token
from .utils import system_payer, awe_mint_public_key, http_client
from awe.settings import settings
import traceback

logger = logging.getLogger("[Collect User Fund Task]")

@app.task
def collect_user_fund(user_deposit_id: int, user_wallet: str, agent_creator_wallet: str, amount: int, game_pool_division: int) -> str:

    pool_amount, agent_creator_amount, developer_amount = settings.tn_share_user_payment(game_pool_division, amount)
    logger.info(f"[User Deposit {user_deposit_id}] collecting user payment: {user_wallet}: {amount}, agent creator: {agent_creator_wallet}, pool: {pool_amount}, creator: {agent_creator_amount}, developer: {developer_amount}")

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

    ixs = []

    if pool_amount != 0:

        # to the pool
        ix_pool = spl_token.transfer_checked(spl_token.TransferCheckedParams(
            source=user_associated_token_account,
            dest=system_payer_associated_token_account,
            owner=system_payer.pubkey(),
            amount=int(pool_amount * 1e9),
            decimals=9,
            mint=awe_mint_public_key,
            program_id=TOKEN_2022_PROGRAM_ID
        ))

        ixs.append(ix_pool)

    if agent_creator_amount != 0:
        # to the agent creator
        ix_agent_creator = spl_token.transfer_checked(spl_token.TransferCheckedParams(
            source=user_associated_token_account,
            dest=agent_creator_associated_token_account,
            owner=system_payer.pubkey(),
            amount=int(agent_creator_amount * 1e9),
            decimals=9,
            mint=awe_mint_public_key,
            program_id=TOKEN_2022_PROGRAM_ID
        ))
        ixs.append(ix_agent_creator)

    # to the developer
    ix_developer = spl_token.transfer_checked(spl_token.TransferCheckedParams(
        source=user_associated_token_account,
        dest=developer_associated_token_account,
        owner=system_payer.pubkey(),
        amount=int(developer_amount * 1e9),
        decimals=9,
        mint=awe_mint_public_key,
        program_id=TOKEN_2022_PROGRAM_ID
    ))
    ixs.append(ix_developer)

    recent_blockhash = http_client.get_latest_blockhash().value.blockhash

    tx = Transaction.new_signed_with_payer(
        ixs,
        system_payer.pubkey(),
        [system_payer],
        recent_blockhash
    )

    logger.info(f"[User Deposit {user_deposit_id}] Sending tx: {tx.signatures[0]}")

    try:
        send_tx_resp = http_client.send_transaction(tx, TxOpts(skip_confirmation=False))
    except Exception as e:
        logger.error(f"[User Deposit {user_deposit_id}] Failed sending the transaction")
        logger.error(e)
        logger.error(traceback.format_exc())
        raise(e)

    tx_hash = str(send_tx_resp.value)
    logger.info(f"[User Deposit {user_deposit_id}] Tx confirmed! {tx_hash}")

    return tx_hash


@app.task
def collect_user_staking(user_staking_id: int, user_wallet: str, amount: int) -> str:
    logger.info(f"[Collect User Staking] [{user_staking_id}] Collecting user staking: {user_wallet}: {amount}")

    system_payer_associated_token_account = spl_token.get_associated_token_address(
        system_payer.pubkey(),
        awe_mint_public_key,
        TOKEN_2022_PROGRAM_ID
    )

    user_wallet_pk = Pubkey.from_string(user_wallet)
    user_associated_token_account = spl_token.get_associated_token_address(
        user_wallet_pk,
        awe_mint_public_key,
        TOKEN_2022_PROGRAM_ID
    )

    ix = spl_token.transfer_checked(spl_token.TransferCheckedParams(
        source=user_associated_token_account,
        dest=system_payer_associated_token_account,
        owner=system_payer.pubkey(),
        amount=int(amount * 1e9),
        decimals=9,
        mint=awe_mint_public_key,
        program_id=TOKEN_2022_PROGRAM_ID
    ))

    recent_blockhash = http_client.get_latest_blockhash().value.blockhash

    tx = Transaction.new_signed_with_payer(
        [ix],
        system_payer.pubkey(),
        [system_payer],
        recent_blockhash
    )

    logger.info(f"[Collect User Staking] [{user_staking_id}] Ready to send tx {tx.signatures[0]}")

    send_tx_resp = http_client.send_transaction(tx, TxOpts(skip_confirmation=False))

    logger.info(f"[Collect User Staking] [{user_staking_id}] Tx confirmed!")

    return str(send_tx_resp.value)


@app.task
def collect_game_pool_charge(charge_id: int, agent_creator_wallet: str, amount: int) -> str:
    logger.info(f"[Game Pool Charge] [{charge_id}] Collecting game pool charge: {agent_creator_wallet}: {amount}")

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

    ix = spl_token.transfer_checked(spl_token.TransferCheckedParams(
        source=agent_creator_associated_token_account,
        dest=system_payer_associated_token_account,
        owner=system_payer.pubkey(),
        amount=int(amount * 1e9),
        decimals=9,
        mint=awe_mint_public_key,
        program_id=TOKEN_2022_PROGRAM_ID
    ))

    recent_blockhash = http_client.get_latest_blockhash().value.blockhash

    tx = Transaction.new_signed_with_payer(
        [ix],
        system_payer.pubkey(),
        [system_payer],
        recent_blockhash
    )

    logger.info(f"[Game Pool Charge] [{charge_id}] Sending tx: {tx.signatures[0]}")

    send_tx_resp = http_client.send_transaction(tx, TxOpts(skip_confirmation=False))

    logger.info(f"[Game Pool Charge] [{charge_id}] Tx confirmed!")

    return str(send_tx_resp.value)
