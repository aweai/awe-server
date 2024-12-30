from awe.settings import settings
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solana.rpc.api import Client
from spl.token.client import Token
from spl.token.constants import TOKEN_2022_PROGRAM_ID

awe_mint_public_key = Pubkey.from_string(settings.solana_awe_mint_address)
system_payer = Keypair.from_base58_string(settings.solana_system_payer_private_key)

http_client = Client(settings.solana_network_endpoint)
token_client = Token(
    http_client,
    awe_mint_public_key,
    TOKEN_2022_PROGRAM_ID,
    system_payer
)
