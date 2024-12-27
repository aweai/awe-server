from ....celery import app
from solders.pubkey import Pubkey
from solders.rpc.responses import GetTokenAccountBalanceResp
from solders.message import Message
from solders.transaction import Transaction
from solders.keypair import Keypair
from solana.rpc.api import Client
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts
from spl.token.client import Token
from spl.token.constants import TOKEN_2022_PROGRAM_ID
import logging
import spl.token.instructions as spl_token
from awe.settings import settings
from awe.celery import app

logger = logging.getLogger("[Transfer to User Task]")

awe_mint_public_key = Pubkey.from_string(settings.solana_awe_mint_address)
system_payer = Keypair.from_base58_string(settings.solana_system_payer_private_key)

logger.info(f"System payer: {str(system_payer.pubkey())}")

http_client = Client(settings.solana_network_endpoint)
token_client = Token(
    http_client,
    awe_mint_public_key,
    TOKEN_2022_PROGRAM_ID,
    system_payer
)

@app.task
def transfer_to_user(user_wallet: str, amount: int):
    # Transfer AWE from the system account to the given wallet address
    # Return the tx address

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

    source_associated_token_account_pubkey = spl_token.get_associated_token_address(
        system_payer.pubkey(),
        awe_mint_public_key,
        TOKEN_2022_PROGRAM_ID
    )

    send_tx_resp = token_client.transfer_checked(
        source=source_associated_token_account_pubkey,
        dest=dest_associated_token_account_pubkey,
        owner=system_payer,
        amount=amount,
        decimals=9
    )

    return str(send_tx_resp)
