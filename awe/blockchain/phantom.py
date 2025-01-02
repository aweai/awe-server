import urllib.parse
from typing import Optional, Tuple
from awe.models.utils import unix_timestamp_in_seconds
from solders.signature import Signature
from solders.pubkey import Pubkey
from nacl.public import PublicKey, Box
from nacl.signing import SigningKey, VerifyKey
from nacl.bindings import crypto_sign_ed25519_sk_to_seed
import base58
import logging
import json
from awe.blockchain import awe_on_chain
from awe.settings import settings

logger = logging.getLogger("[Phantom Wallet]")

comm_ed25519_seed = crypto_sign_ed25519_sk_to_seed(base58.b58decode(settings.comm_ed25519_private_key))

comm_ed25519_public_key = VerifyKey(base58.b58decode(settings.comm_ed25519_public_key))
comm_ed25519_private_key = SigningKey(comm_ed25519_seed)

comm_x25519_public_key_str = base58.b58encode(bytes(comm_ed25519_public_key.to_curve25519_public_key())).decode()
comm_x25519_private_key = comm_ed25519_private_key.to_curve25519_private_key()

def get_connect_url(agent_id: int, tg_user_id: str) -> str:

    app_url = urllib.parse.quote_plus("https://aweai.fun")

    # Generate a signature from the server to prevent middleman attack
    timestamp = unix_timestamp_in_seconds()
    signature = sign_comm_message(f"{agent_id}{tg_user_id}{timestamp}")

    redirect_link = urllib.parse.quote_plus(f"{settings.server_host}/v1/tg-phantom-wallets/connect/{agent_id}/{tg_user_id}?timestamp={timestamp}&signature={signature}")

    return f"https://phantom.app/ul/v1/connect?app_url={app_url}&dapp_encryption_public_key={comm_x25519_public_key_str}&redirect_link={redirect_link}&cluster={settings.solana_network}"

def get_browser_connect_url(agent_id: int, tg_user_id: str, tg_bot_username: str) -> str:
    # Generate a signature from the server to prevent middleman attack
    timestamp = unix_timestamp_in_seconds()
    signature = sign_comm_message(f"{agent_id}{tg_user_id}{timestamp}")

    return f"{settings.webui_host}/callback/user-wallets/bind/{agent_id}/{tg_user_id}?timestamp={timestamp}&signature={signature}&tg_bot={tg_bot_username}"

def get_approve_url(
        action: str,
        agent_id: int,
        tg_user_id: str,
        amount: int,
        user_wallet: str,
        phantom_session: str,
        phantom_encryption_public_key: str
    ) -> str:

    transaction = awe_on_chain.get_user_approve_transaction(user_wallet, amount)

    plain_payload = json.dumps({
        "transaction": base58.b58encode(transaction).decode(),
        "session": phantom_session
    })

    logger.debug(f"plain payload str: {plain_payload}")

    redirect_link = urllib.parse.quote_plus(f"{settings.server_host}/v1/tg-phantom-wallets/approve/{agent_id}/{tg_user_id}?action={action}&amount={amount}")
    encrypted_payload, nonce = encrypt_phantom_data(phantom_encryption_public_key, plain_payload)

    return f"https://phantom.app/ul/v1/signAndSendTransaction?dapp_encryption_public_key={comm_x25519_public_key_str}&nonce={nonce}&redirect_link={redirect_link}&payload={encrypted_payload}"

def get_browser_approve_url(
        action: str,
        agent_id: int,
        tg_user_id: str,
        user_wallet: str,
        amount: int,
        tg_bot_username: str
    ):
    return f"{settings.webui_host}/callback/user-wallets/approve/{agent_id}/{tg_user_id}/{user_wallet}?amount={amount}&tg_bot={tg_bot_username}&action={action}"

def get_wallet_verification_url(agent_id: int, tg_user_id: str, wallet_address: str, phantom_session: str, phantom_encryption_public_key: str) -> str:

    # Generate a signature from the server to prevent middleman attack
    timestamp = unix_timestamp_in_seconds()
    signature = sign_comm_message(f"{agent_id}{tg_user_id}{wallet_address}{timestamp}")

    redirect_link = urllib.parse.quote_plus(f"{settings.server_host}/v1/tg-phantom-wallets/verify/{agent_id}/{tg_user_id}?wallet={wallet_address}&timestamp={timestamp}&signature={signature}")

    original_message = f"{timestamp}"
    original_message_encoded = base58.b58encode(original_message.encode()).decode()

    plain_payload = json.dumps({
        "message": original_message_encoded,
        "session": phantom_session
    })

    encrypted_payload, nonce = encrypt_phantom_data(phantom_encryption_public_key, plain_payload)

    return f"https://phantom.app/ul/v1/signMessage?dapp_encryption_public_key={comm_x25519_public_key_str}&nonce={nonce}&redirect_link={redirect_link}&payload={encrypted_payload}"


def sign_comm_message(data_to_sign: str) -> str:
    signed = comm_ed25519_private_key.sign(data_to_sign.encode())
    return base58.b58encode(signed.signature).decode()


def verify_comm_signature(data_to_sign: str, timestamp: int, signature: str) -> Optional[str]:
    current_timestamp = unix_timestamp_in_seconds()
    if current_timestamp - timestamp >= 180:
        return "Timestamp too old"
    sig_bytes = base58.b58decode(signature)

    try:
        comm_ed25519_public_key.verify(data_to_sign.encode(), sig_bytes)
    except:
        return "Invalid communication signature"

    return None


def verify_solana_signature(data_to_sign: str, pubkey: Pubkey, signature: str) -> Optional[str]:
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
    return Box(comm_x25519_private_key, phantom_public_key)
