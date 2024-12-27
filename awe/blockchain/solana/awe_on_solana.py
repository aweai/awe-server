from ..awe_onchain import AweOnChain
from solders.signature import Signature
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.rpc.responses import GetTokenAccountBalanceResp
from solders.message import Message
from solders.transaction import Transaction
import os
from solana.rpc.api import Client
from solana.rpc.commitment import Confirmed, Finalized
from solana.rpc.types import TxOpts
from spl.token.client import Token
from spl.token.constants import TOKEN_2022_PROGRAM_ID
import logging
import spl.token.instructions as spl_token
import time

SOLANA_NETWORK_ENDPOINTS = {
    "devnet": "https://api.devnet.solana.com",
    "mainnet": "https://api.mainnet-beta.solana.com",
    "testnet": "https://api.testnet.solana.com"
}

class AweOnSolana(AweOnChain):

    def __init__(self) -> None:
        super().__init__()

        self.logger = logging.getLogger("[Sol Client]")

        network = os.getenv("SOLANA_NETWORK", "")
        if network == "" or network not in SOLANA_NETWORK_ENDPOINTS.keys():
            raise Exception("SOLANA_NETWORK is not specified correctly in env file")

        self.awe_metadata_address = os.getenv("SOLANA_AWE_METADATA_ADDRESS", "")
        if self.awe_metadata_address == "":
            raise Exception("SOLANA_AWE_METADATA_ADDRESS is not specified in env file")

        self.awe_mint_address = os.getenv("SOLANA_AWE_MINT_ADDRESS", "")
        if self.awe_mint_address == "":
            raise Exception("SOLANA_AWE_MINT_ADDRESS is not specified in env file")

        program_id_address = os.getenv("SOLANA_AWE_PROGRAM_ID", "")
        if program_id_address == "":
            raise Exception("SOLANA_AWE_PROGRAM_ID is not specified in env file")

        system_payer_private_key = os.getenv("SOLANA_SYSTEM_PAYER_PRIVATE_KEY", "")
        if system_payer_private_key == "":
            raise Exception("SOLANA_SYSTEM_PAYER_PRIVATE_KEY is not specified in env file")

        self.program_id = Pubkey.from_string(program_id_address)
        self.awe_metadata_public_key = Pubkey.from_string(self.awe_metadata_address)
        self.awe_mint_public_key = Pubkey.from_string(self.awe_mint_address)
        self.system_payer = Keypair.from_base58_string(system_payer_private_key)
        self.logger.info(f"System payer: {str(self.system_payer.pubkey())}")
        self.http_client = Client(SOLANA_NETWORK_ENDPOINTS[network])
        self.token_client = Token(
            self.http_client,
            self.awe_mint_public_key,
            TOKEN_2022_PROGRAM_ID,
            self.system_payer
        )


    def get_user_num_agents(self, address: str) -> int:

        user_public_key = Pubkey.from_string(address)

        agent_account_public_key, _ = Pubkey.find_program_address(
            [b"agent_creator", bytes(self.awe_metadata_public_key), bytes(user_public_key)],
            self.program_id
        )
        account_data = self.http_client.get_account_info(
            pubkey=agent_account_public_key,
        )

        if account_data.value is None:
            return 0

        account_data_bytes = bytearray(account_data.value.data)
        return int(account_data_bytes[len(account_data_bytes) - 1])


    def validate_signature(self, public_key: str, message: str, signature: str) -> str | None:
        # Validate the signature and return the address
        # Return None if validation failed
        pk = Pubkey.from_string(public_key)
        signature = Signature.from_string(signature)
        message_bytes = message.encode()
        if signature.verify(pk, message_bytes):
            return public_key

        return None


    def transfer_token(self, dest_owner_address: str, amount: int) -> str:
        # Transfer AWE from the system account to the given wallet address
        # Return the tx address

        dest_owner_pubkey = Pubkey.from_string(dest_owner_address)

        dest_associated_token_account_pubkey = spl_token.get_associated_token_address(
            dest_owner_pubkey,
            self.awe_mint_public_key,
            TOKEN_2022_PROGRAM_ID
        )


        resp = self.token_client.get_balance(
            dest_associated_token_account_pubkey,
            Confirmed
        )

        if not isinstance(resp, GetTokenAccountBalanceResp):
            # Token account not exist
            # We have to create it for the user
            # Some SOL will be spent

            ix = spl_token.create_associated_token_account(
                payer=self.system_payer.pubkey(),
                owner=dest_owner_pubkey,
                mint=self.awe_mint_public_key,
                token_program_id=TOKEN_2022_PROGRAM_ID
            )

            recent_blockhash = self.http_client.get_latest_blockhash().value.blockhash
            msg = Message.new_with_blockhash([ix], self.system_payer.pubkey(), recent_blockhash)

            txn = Transaction([self.system_payer], msg, recent_blockhash)
            tx_opts = TxOpts(skip_confirmation=False)
            self.http_client.send_transaction(txn, opts=tx_opts)

        source_associated_token_account_pubkey = spl_token.get_associated_token_address(
            self.system_payer.pubkey(),
            self.awe_mint_public_key,
            TOKEN_2022_PROGRAM_ID
        )

        send_tx_resp = self.token_client.transfer_checked(
            source=source_associated_token_account_pubkey,
            dest=dest_associated_token_account_pubkey,
            owner=self.system_payer,
            amount=amount,
            decimals=9
        )

        return send_tx_resp.to_json()


    def get_balance(self, owner_address: str) -> int:
        # Get the balance of the given owner
        # Return the balance
        owner = Pubkey.from_string(owner_address)

        associated_token_account_pubkey = spl_token.get_associated_token_address(
            owner,
            self.awe_mint_public_key,
            TOKEN_2022_PROGRAM_ID
        )

        resp = self.token_client.get_balance(
            associated_token_account_pubkey,
            Confirmed
        )

        if isinstance(resp, GetTokenAccountBalanceResp):
            amount_str = resp.value.amount
            return int(amount_str)
        else:
            # Token account not exist
            return 0

    def get_system_payer(self) -> str:
        # Get the address of the system account
        return str(self.system_payer.pubkey())

    def is_valid_address(self, address: str) -> bool:
        try:
            decoded = Pubkey.from_string(address)
            return decoded.is_on_curve()
        except:
            return False

    def get_user_approve_transaction(self, user_wallet: str, amount: int) -> bytes:
        # Construct a tx for the user to approve the system delegate account to transfer certain amount of tokens.
        user_wallet_pk = Pubkey.from_string(user_wallet)

        user_associated_token_account = spl_token.get_associated_token_address(
            user_wallet_pk,
            self.awe_mint_public_key,
            TOKEN_2022_PROGRAM_ID
        )

        params = spl_token.ApproveCheckedParams(
            program_id=TOKEN_2022_PROGRAM_ID,
            source=user_associated_token_account,
            mint=self.awe_mint_public_key,
            delegate=self.system_payer.pubkey(),
            owner=user_wallet_pk,
            amount=int(amount * 1e9),
            decimals=9
        )

        ix = spl_token.approve_checked(params)

        recent_blockhash = self.http_client.get_latest_blockhash().value.blockhash
        msg = Message.new_with_blockhash([ix], user_wallet_pk, recent_blockhash)

        tx = Transaction.new_unsigned(msg)
        return bytes(tx)


    def collect_user_payment(self, user_wallet: str, amount: int):
        # Transfer tokens from the user wallet to the system wallet
        # Return the transaction hash

        self.logger.debug(f"collecting user payment: {user_wallet}: {amount}")

        system_payer_associated_token_account = spl_token.get_associated_token_address(
            self.system_payer.pubkey(),
            self.awe_mint_public_key,
            TOKEN_2022_PROGRAM_ID
        )

        user_wallet_pk = Pubkey.from_string(user_wallet)
        user_associated_token_account = spl_token.get_associated_token_address(
            user_wallet_pk,
            self.awe_mint_public_key,
            TOKEN_2022_PROGRAM_ID
        )

        self.logger.debug(f"source: {str(user_associated_token_account)}, dest: {str(system_payer_associated_token_account)}")
        self.logger.debug(f"signer: {str(self.system_payer.pubkey())}")

        send_tx_resp = self.token_client.transfer_checked(
            source=user_associated_token_account,
            dest=system_payer_associated_token_account,
            owner=self.system_payer,
            amount=int(amount * 1e9),
            decimals=9,
            opts=TxOpts(
                skip_confirmation=False
            )
        )

        return str(send_tx_resp)


    def wait_for_tx_confirmation(self, tx_hash: str, timeout: int):
        # Wait for the confirmation of the given tx
        # Or timeout
        count = 0
        sig = Signature.from_string(tx_hash)
        while(True):
            try:
                tx = self.http_client.get_transaction(tx_sig=sig, commitment=Finalized)
                if tx.value is not None:
                    self.logger.debug("Transaction confirmed")
                    self.logger.debug(tx.to_json())
                    return
                else:
                    self.logger.debug("Transaction not confirmed")
            except Exception as e:
                self.logger.error("Error getting confirmed tx")
                self.logger.error(e)

            count += 1
            if count >= timeout:
                raise Exception("Transaction timeout!")

            time.sleep(1)
