from ....celery import app
import logging
from solders.pubkey import Pubkey
from solders.transaction import Transaction
from solana.rpc.types import TxOpts
from spl.token.constants import TOKEN_2022_PROGRAM_ID
import spl.token.instructions as spl_token
from .utils import system_payer, awe_mint_public_key, http_client
import traceback
from typing import Tuple

logger = logging.getLogger("[Collect User Fund Task]")

@app.task
def collect_user_fund(user_deposit_id: int, user_wallet: str, amount: int) -> Tuple[str, int]:

    logger.info(f"[User Deposit {user_deposit_id}] Collecting user deposit: {user_wallet}: {amount}")

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

    logger.debug(f"source: {str(user_associated_token_account)}, target: {str(system_payer_associated_token_account)}")
    logger.debug(f"signer: {str(system_payer.pubkey())}")

    ix = spl_token.transfer_checked(spl_token.TransferCheckedParams(
        source=user_associated_token_account,
        dest=system_payer_associated_token_account,
        owner=system_payer.pubkey(),
        amount=int(amount * 1e9),
        decimals=9,
        mint=awe_mint_public_key,
        program_id=TOKEN_2022_PROGRAM_ID
    ))

    latest_blockhash = http_client.get_latest_blockhash().value

    recent_blockhash = latest_blockhash.blockhash
    last_valid_block_height = latest_blockhash.last_valid_block_height

    tx = Transaction.new_signed_with_payer(
        [ix],
        system_payer.pubkey(),
        [system_payer],
        recent_blockhash
    )

    logger.info(f"[User Deposit {user_deposit_id}] Sending tx: {tx.signatures[0]}")

    try:
        send_tx_resp = http_client.send_transaction(tx, TxOpts(skip_confirmation=True))
    except Exception as e:
        logger.error(f"[User Deposit {user_deposit_id}] Failed sending the transaction")
        logger.error(e)
        logger.error(traceback.format_exc())
        raise(e)

    tx_hash = str(send_tx_resp.value)
    logger.info(f"[User Deposit {user_deposit_id}] Tx sent! {tx_hash}")

    return tx_hash, last_valid_block_height


@app.task
def collect_user_staking(user_staking_id: int, user_wallet: str, amount: int) -> Tuple[str, int]:
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

    latest_blockhash = http_client.get_latest_blockhash().value

    recent_blockhash = latest_blockhash.blockhash
    last_valid_block_height = latest_blockhash.last_valid_block_height

    tx = Transaction.new_signed_with_payer(
        [ix],
        system_payer.pubkey(),
        [system_payer],
        recent_blockhash
    )

    logger.info(f"[Collect User Staking] [{user_staking_id}] Ready to send tx {tx.signatures[0]}")

    send_tx_resp = http_client.send_transaction(tx, TxOpts(skip_confirmation=True))

    logger.info(f"[Collect User Staking] [{user_staking_id}] Tx sent!")

    return str(send_tx_resp.value), last_valid_block_height


@app.task
def collect_agent_creation_staking(creation_id: int, address: str, amount: int) -> Tuple[str, int]:

    logger.info(f"[Agent Creation Staking] [{creation_id}] Collecting agent creation staking: {address}: {amount}")

    system_payer_associated_token_account = spl_token.get_associated_token_address(
        system_payer.pubkey(),
        awe_mint_public_key,
        TOKEN_2022_PROGRAM_ID
    )

    agent_creator_pub_key = Pubkey.from_string(address)
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

    latest_blockhash = http_client.get_latest_blockhash().value

    recent_blockhash = latest_blockhash.blockhash
    last_valid_block_height = latest_blockhash.last_valid_block_height

    tx = Transaction.new_signed_with_payer(
        [ix],
        system_payer.pubkey(),
        [system_payer],
        recent_blockhash
    )

    logger.info(f"[Agent Creation Staking] [{creation_id}] Sending tx: {tx.signatures[0]}")

    send_tx_resp = http_client.send_transaction(tx, TxOpts(skip_confirmation=True))

    logger.info(f"[Agent Creation Staking] [{creation_id}] Tx sent!")

    return str(send_tx_resp.value), last_valid_block_height



@app.task
def collect_game_pool_charge(charge_id: int, agent_creator_wallet: str, amount: int) -> Tuple[str, int]:
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

    latest_blockhash = http_client.get_latest_blockhash().value

    recent_blockhash = latest_blockhash.blockhash
    last_valid_block_height = latest_blockhash.last_valid_block_height

    tx = Transaction.new_signed_with_payer(
        [ix],
        system_payer.pubkey(),
        [system_payer],
        recent_blockhash
    )

    logger.info(f"[Game Pool Charge] [{charge_id}] Sending tx: {tx.signatures[0]}")

    send_tx_resp = http_client.send_transaction(tx, TxOpts(skip_confirmation=True))

    logger.info(f"[Game Pool Charge] [{charge_id}] Tx sent!")

    return str(send_tx_resp.value), last_valid_block_height
