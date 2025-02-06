from ....celery import app
from solders.pubkey import Pubkey
from solders.rpc.responses import GetTokenAccountBalanceResp
from solders.message import Message
from solders.transaction import Transaction
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts
from spl.token.constants import TOKEN_2022_PROGRAM_ID
import logging
import spl.token.instructions as spl_token
from awe.celery import app
from .utils import token_client, awe_mint_public_key, system_payer, http_client
from typing import List, Tuple


logger = logging.getLogger("[Transfer to User Task]")


@app.task
def transfer_to_user(request_id: str, user_wallet: str, amount: int) -> Tuple[str, int]:
    # Transfer AWE from the system account to the given wallet address
    # Return the tx address and last valid block height

    logger.info(f"[Request {request_id}] Start transfering to user")

    dest_owner_pubkey = Pubkey.from_string(user_wallet)

    dest_associated_token_account_pubkey = spl_token.get_associated_token_address(
        dest_owner_pubkey,
        awe_mint_public_key,
        TOKEN_2022_PROGRAM_ID
    )

    resp = token_client.get_balance(
        dest_associated_token_account_pubkey,
        Confirmed
    )

    if not isinstance(resp, GetTokenAccountBalanceResp):
        # Token account not exist
        # We have to create it for the user
        # Some SOL will be spent

        logger.info(f"[Request {request_id}] Create token account for the user")

        ix = spl_token.create_associated_token_account(
            payer=system_payer.pubkey(),
            owner=dest_owner_pubkey,
            mint=awe_mint_public_key,
            token_program_id=TOKEN_2022_PROGRAM_ID
        )

        recent_blockhash = http_client.get_latest_blockhash().value.blockhash
        msg = Message.new_with_blockhash([ix], system_payer.pubkey(), recent_blockhash)

        txn = Transaction([system_payer], msg, recent_blockhash)
        tx_opts = TxOpts(skip_confirmation=False)
        http_client.send_transaction(txn, opts=tx_opts)

        logger.info(f"[Request {request_id}] User token account created!")

    source_associated_token_account_pubkey = spl_token.get_associated_token_address(
        system_payer.pubkey(),
        awe_mint_public_key,
        TOKEN_2022_PROGRAM_ID
    )

    logger.info(f"[Request {request_id}] Ready to send tx")

    latest_blockhash = http_client.get_latest_blockhash().value

    recent_blockhash = latest_blockhash.blockhash
    last_valid_block_height = latest_blockhash.last_valid_block_height

    send_tx_resp = token_client.transfer_checked(
        source=source_associated_token_account_pubkey,
        dest=dest_associated_token_account_pubkey,
        owner=system_payer,
        amount=int(amount * 1e9),
        decimals=9,
        recent_blockhash=recent_blockhash
    )

    logger.info(f"[Request {request_id}] Tx sent {send_tx_resp.value}")

    return str(send_tx_resp.value), last_valid_block_height


@app.task
def batch_transfer_to_users(user_wallets: List[str], amounts: List[int]):

    if len(user_wallets) != len(amounts):
        raise Exception("Mismatched addresses and amounts")

    if len(user_wallets) == 0:
        raise Exception("Empty user addresses given")

    source_associated_token_account_pubkey = spl_token.get_associated_token_address(
        system_payer.pubkey(),
        awe_mint_public_key,
        TOKEN_2022_PROGRAM_ID
    )

    ixs = []

    for idx, address in enumerate(user_wallets):
        dest_owner_pubkey = Pubkey.from_string(address)

        # The dest account should have existed since it has paid AWE before
        dest_associated_token_account_pubkey = spl_token.get_associated_token_address(
            dest_owner_pubkey,
            awe_mint_public_key,
            TOKEN_2022_PROGRAM_ID
        )

        transfer_ix = spl_token.transfer_checked(
            spl_token.TransferCheckedParams(
                source=source_associated_token_account_pubkey,
                dest=dest_associated_token_account_pubkey,
                amount=amounts[idx] * 1e9,
                mint=awe_mint_public_key,
                program_id=TOKEN_2022_PROGRAM_ID,
                decimals=9,
                owner=system_payer
            )
        )

        ixs.append(transfer_ix)

    recent_blockhash = http_client.get_latest_blockhash().value.blockhash
    msg = Message.new_with_blockhash(ixs, system_payer.pubkey(), recent_blockhash)

    txn = Transaction([system_payer], msg, recent_blockhash)
    tx_opts = TxOpts(skip_confirmation=False)

    send_tx_resp = http_client.send_transaction(txn, opts=tx_opts)
    return str(send_tx_resp.value)
