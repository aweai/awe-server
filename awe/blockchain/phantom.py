import urllib.parse
import os
from typing import Optional, Tuple
from awe.models.utils import unix_timestamp_in_seconds
from solders.keypair import Keypair
from solders.signature import Signature
from solders.pubkey import Pubkey
from nacl.public import PrivateKey, PublicKey, Box
from nacl.bindings.crypto_sign import crypto_sign_ed25519_pk_to_curve25519, crypto_sign_ed25519_sk_to_curve25519
import base58
import logging
import json
from awe.blockchain import awe_on_chain

logger = logging.getLogger("[Phantom Wallet]")

server_host = os.getenv("SERVER_HOST", "")
if server_host == "":
    raise Exception("SERVER_HOST is not set")

system_payer_private_key = os.getenv("SOLANA_SYSTEM_PAYER_PRIVATE_KEY", "")
if system_payer_private_key == "":
    raise Exception("SOLANA_SYSTEM_PAYER_PRIVATE_KEY is not set")

system_payer = Keypair.from_base58_string(system_payer_private_key)
system_payer_x25519_public_key_str = base58.b58encode(crypto_sign_ed25519_pk_to_curve25519(bytes(system_payer.pubkey()))).decode()
system_payer_x25519_private_key = PrivateKey(crypto_sign_ed25519_sk_to_curve25519(base58.b58decode(system_payer_private_key)))

def get_connect_url(agent_id: int, tg_user_id: str) -> str:

    app_url = urllib.parse.quote_plus("https://aweai.fun")

    # Generate a signature from the server to prevent middleman attack
    timestamp = unix_timestamp_in_seconds()
    data_to_sign = f"{agent_id}{tg_user_id}{timestamp}"
    signature = str(system_payer.sign_message(data_to_sign.encode()))

    redirect_link = urllib.parse.quote_plus(f"{server_host}/v1/tg-phantom-wallets/connect/{agent_id}/{tg_user_id}?timestamp={timestamp}&signature={signature}")

    cluster = os.getenv("SOLANA_NETWORK", "devnet")
    return f"https://phantom.app/ul/v1/connect?app_url={app_url}&dapp_encryption_public_key={system_payer_x25519_public_key_str}&redirect_link={redirect_link}&cluster={cluster}"

def get_approve_url(agent_id: int, tg_user_id: str, amount: int, user_wallet: str, phantom_session: str, phantom_encryption_public_key: str) -> str:

    transaction = awe_on_chain.get_user_approve_transaction(user_wallet, amount)

    plain_payload = json.dumps({
        "transaction": base58.b58encode(transaction).decode(),
        "session": phantom_session
    })

    logger.debug(f"plain payload str: {plain_payload}")

    redirect_link = urllib.parse.quote_plus(f"{server_host}/v1/tg-phantom-wallets/approve/{agent_id}/{tg_user_id}")
    encrypted_payload, nonce = encrypt_phantom_data(phantom_encryption_public_key, plain_payload)

    return f"https://phantom.app/ul/v1/signAndSendTransaction?dapp_encryption_public_key={system_payer_x25519_public_key_str}&nonce={nonce}&redirect_link={redirect_link}&payload={encrypted_payload}"

def get_wallet_verification_url(agent_id: int, tg_user_id: str, wallet_address: str, phantom_session: str, phantom_encryption_public_key: str) -> str:

    # Generate a signature from the server to prevent middleman attack
    timestamp = unix_timestamp_in_seconds()
    data_to_sign = f"{agent_id}{tg_user_id}{wallet_address}{timestamp}"
    signature = str(system_payer.sign_message(data_to_sign.encode()))

    redirect_link = urllib.parse.quote_plus(f"{server_host}/v1/tg-phantom-wallets/verify/{agent_id}/{tg_user_id}?wallet={wallet_address}&timestamp={timestamp}&signature={signature}")

    original_message = f"{timestamp}"
    original_message_encoded = base58.b58encode(original_message.encode()).decode()

    plain_payload = json.dumps({
        "message": original_message_encoded,
        "session": phantom_session
    })

    encrypted_payload, nonce = encrypt_phantom_data(phantom_encryption_public_key, plain_payload)

    return f"https://phantom.app/ul/v1/signMessage?dapp_encryption_public_key={system_payer_x25519_public_key_str}&nonce={nonce}&redirect_link={redirect_link}&payload={encrypted_payload}"


def verify_system_signature(data_to_sign: str, timestamp: int, signature: str) -> Optional[str]:
    current_timestamp = unix_timestamp_in_seconds()
    if current_timestamp - timestamp >= 180:
        return "Timestamp too old"

    return verify_signature(data_to_sign, system_payer.pubkey(), signature)


def verify_signature(data_to_sign: str, pubkey: Pubkey, signature: str) -> Optional[str]:
    sig = Signature.from_string(signature)
    if not sig.verify(pubkey, data_to_sign.encode()):
        return "Invalid signature"

    return None

def encrypt_phantom_data(phantom_encryption_public_key: str, plain_data: str) -> Tuple[str, str]:

    data_box = get_databox(phantom_encryption_public_key)

    encrypted = data_box.encrypt(plain_data.encode())
    encrypted_ciphertext = base58.b58encode(encrypted.ciphertext).decode()
    nonce = base58.b58encode(encrypted.nonce).decode()

    return encrypted_ciphertext, nonce


def decrypt_phantom_data(phantom_encryption_public_key: str, nonce: str, encrypted_data: str) -> str:

    data_box = get_databox(phantom_encryption_public_key)

    nonce_bytes = base58.b58decode(nonce)
    data_bytes = base58.b58decode(encrypted_data)

    decrypted_data = data_box.decrypt(data_bytes, nonce_bytes)

    return decrypted_data.decode()

def get_databox(phantom_encryption_public_key: str) -> Box:
    phantom_public_key_bytes = base58.b58decode(phantom_encryption_public_key)
    phantom_public_key = PublicKey(phantom_public_key_bytes)
    return Box(system_payer_x25519_private_key, phantom_public_key)
