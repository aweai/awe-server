import urllib.parse
import os
from typing import Optional, Tuple
from awe.models.utils import unix_timestamp_in_seconds
from solders.keypair import Keypair
from solders.signature import Signature
from nacl.public import PrivateKey, PublicKey, Box
from nacl.bindings.crypto_sign import crypto_sign_ed25519_pk_to_curve25519, crypto_sign_ed25519_sk_to_curve25519
import base58
import logging
import json

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


def get_wallet_verification_url(agent_id: int, tg_user_id: str, wallet_address: str, phantom_session: str, phantom_encryption_public_key: str) -> str:

    ed25519_public_key_bytes = bytes(system_payer.pubkey())
    x25519_public_key = base58.b58encode(crypto_sign_ed25519_pk_to_curve25519(ed25519_public_key_bytes)).decode()

    # Generate a signature from the server to prevent middleman attack
    timestamp = unix_timestamp_in_seconds()
    data_to_sign = f"{agent_id}{tg_user_id}{wallet_address}{timestamp}"
    signature = str(system_payer.sign_message(data_to_sign.encode()))

    redirect_link = urllib.parse.quote_plus(f"{server_host}/v1/tg-phantom-wallets/verify/{agent_id}/{tg_user_id}?wallet={wallet_address}&timestamp={timestamp}&signature={signature}")

    original_message = f"{timestamp}"
    original_message_encoded = base58.b58encode(original_message).decode()

    plain_payload = json.dumps({
        "message": original_message_encoded,
        "session": phantom_session
    })

    logger.debug(f"plain payload str: {plain_payload}")

    encrypted_payload, nonce = encrypt_phantom_data(phantom_encryption_public_key, plain_payload)

    logger.debug(f"encrypted payload: {encrypted_payload}")
    logger.debug(f"nonce: {nonce}")

    # Debug - try decrypting
    decrypted = decrypt_phantom_data(phantom_encryption_public_key, nonce, encrypted_payload)
    logger.debug(f"decrypted: {decrypted}")

    return f"https://phantom.app/ul/v1/signMessage?dapp_encryption_public_key={x25519_public_key}&nonce={nonce}&redirect_link={redirect_link}&payload={encrypted_payload}"


def verify_signature(data_to_sign: str, timestamp: int, signature: str) -> Optional[str]:
    current_timestamp = unix_timestamp_in_seconds()
    if current_timestamp - timestamp >= 180:
        return "Timestamp too old"

    sig = Signature.from_string(signature)
    if not sig.verify(system_payer.pubkey(), data_to_sign.encode()):
        return "Invalid signature"

    return None


def encrypt_phantom_data(phantom_encryption_public_key: str, plain_data: str) -> Tuple[str, str]:
    system_payer_private_key_bytes = base58.b58decode(system_payer_private_key)

    x25519_private_key_bytes = crypto_sign_ed25519_sk_to_curve25519(system_payer_private_key_bytes)
    x25519_private_key = PrivateKey(x25519_private_key_bytes)

    phantom_public_key_bytes = base58.b58decode(phantom_encryption_public_key)
    phantom_public_key = PublicKey(phantom_public_key_bytes)

    data_box = Box(x25519_private_key, phantom_public_key)
    encrypted = data_box.encrypt(plain_data.encode())
    encrypted_ciphertext = base58.b58encode(encrypted.ciphertext).decode()
    nonce = base58.b58encode(encrypted.nonce).decode()

    return encrypted_ciphertext, nonce


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
