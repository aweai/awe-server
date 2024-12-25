import urllib.parse
import os
from typing import Optional
from awe.models.utils import unix_timestamp_in_seconds
from solders.keypair import Keypair
from solders.signature import Signature
from nacl.public import PrivateKey, PublicKey, Box
from nacl.bindings.crypto_sign import crypto_sign_ed25519_pk_to_curve25519, crypto_sign_ed25519_sk_to_curve25519
import base58
import logging

logger = logging.getLogger("[Phantom Wallet]")

server_host = os.getenv("SERVER_HOST", "")
if server_host == "":
    raise Exception("SERVER_HOST is not set")

system_payer_private_key = os.getenv("SOLANA_SYSTEM_PAYER_PRIVATE_KEY", "")
if system_payer_private_key == "":
    raise Exception("SOLANA_SYSTEM_PAYER_PRIVATE_KEY is not set")
system_payer = Keypair.from_base58_string(system_payer_private_key)

def get_connect_url(agent_id: int, tg_user_id: str) -> str:

    app_url = urllib.parse.quote_plus("https://aweai.fun")
    ed25519_public_key_bytes = bytes(system_payer.pubkey())
    x25519_public_key = base58.b58encode(crypto_sign_ed25519_pk_to_curve25519(ed25519_public_key_bytes)).decode()

    # Generate a signature from the server to prevent middleman attack
    timestamp = unix_timestamp_in_seconds()
    data_to_sign = f"{agent_id}{tg_user_id}{timestamp}"
    signature = str(system_payer.sign_message(data_to_sign.encode()))

    redirect_link = urllib.parse.quote_plus(f"{server_host}/v1/tg-phantom-wallets/connect/{agent_id}/{tg_user_id}?timestamp={timestamp}&signature={signature}")
    return f"https://phantom.app/ul/v1/connect?app_url={app_url}&dapp_encryption_public_key={x25519_public_key}&redirect_link={redirect_link}"

def verify_wallet(agent_id: int, tg_user_id: str, signed_message: str):
    pass

def verify_signature(agent_id: int, tg_user_id: str, timestamp: int, signature: str) -> Optional[str]:
    current_timestamp = unix_timestamp_in_seconds()
    if current_timestamp - timestamp >= 60:
        return "Timestamp too old"

    data_to_sign = f"{agent_id}{tg_user_id}{timestamp}"
    sig = Signature.from_string(signature)
    if not sig.verify(system_payer.pubkey(), data_to_sign.encode()):
        return "Invalid signature"

    return None

def decrypt_phantom_data(phantom_encryption_public_key: str, nonce: str, encrypted_data: str) -> str:

    system_payer_private_key_bytes = base58.b58decode(system_payer_private_key)

    x25519_private_key_bytes = crypto_sign_ed25519_sk_to_curve25519(system_payer_private_key_bytes)
    x25519_private_key = PrivateKey(x25519_private_key_bytes)

    phantom_public_key_bytes = base58.b58decode(phantom_encryption_public_key)
    phantom_public_key = PublicKey(phantom_public_key_bytes)

    nonce_bytes = base58.b58decode(nonce)

    data_bytes = base58.b58decode(encrypted_data)

    data_box = Box(x25519_private_key, phantom_public_key)
    decrypted_data = data_box.decrypt(data_bytes, nonce_bytes)
    return decrypted_data.decode()
