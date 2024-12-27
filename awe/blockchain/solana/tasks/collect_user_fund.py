from ....celery import app
import logging
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from spl.token.client import Token
from spl.token.constants import TOKEN_2022_PROGRAM_ID
import spl.token.instructions as spl_token

from awe.settings import settings

logger = logging.getLogger("[Collect User Fund Task]")

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
def collect_user_fund(user_wallet: str, amount: int) -> str:
    logger.debug(f"collecting user payment: {user_wallet}: {amount}")

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

    logger.debug(f"source: {str(user_associated_token_account)}, dest: {str(system_payer_associated_token_account)}")
    logger.debug(f"signer: {str(system_payer.pubkey())}")

    send_tx_resp = token_client.transfer_checked(
        source=user_associated_token_account,
        dest=system_payer_associated_token_account,
        owner=system_payer,
        amount=int(amount * 1e9),
        decimals=9,
        opts=TxOpts(
            skip_confirmation=False
        )
    )

    return str(send_tx_resp.value)
