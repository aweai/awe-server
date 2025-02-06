from ..awe_onchain import AweOnChain
from solders.signature import Signature
from solders.pubkey import Pubkey
from solders.rpc.responses import GetTokenAccountBalanceResp
from solders.message import Message
from solders.transaction import Transaction
from solana.rpc.api import Client
from solana.rpc.commitment import Confirmed, Finalized
from spl.token.constants import TOKEN_2022_PROGRAM_ID
import logging
import spl.token.instructions as spl_token
import time
from awe.settings import settings
from awe.celery import app
from typing import List

class AweOnSolana(AweOnChain):

    def __init__(self) -> None:
        super().__init__()

        self.logger = logging.getLogger("[Sol Client]")

        self.program_id = Pubkey.from_string(settings.solana_awe_program_id)
        self.awe_metadata_public_key = Pubkey.from_string(settings.solana_awe_metadata_address)
        self.awe_mint_public_key = Pubkey.from_string(settings.solana_awe_mint_address)
        self.system_payer_public_key = Pubkey.from_string(settings.solana_system_payer_public_key)

        self.logger.info(f"System payer: {str(self.system_payer_public_key)}")

        self.http_client = Client(settings.solana_network_endpoint)


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


    def transfer_to_user(self, dest_owner_address: str, amount: int) -> str:
        # Transfer AWE from the system account to the given wallet address
        # Return the tx address
        task = app.send_task(
            name='awe.blockchain.solana.tasks.transfer_to_user.transfer_to_user',
            args=(dest_owner_address, amount)
        )
        self.logger.info("Sent transfer to user task to the queue")
        return task.get()


    def batch_transfer_to_users(self, owner_addresses: List[str], amounts: List[int]) -> str:
        # Transfer AWE from the system account to the list of given wallet address
        # Return the tx address
        task = app.send_task(
            name='awe.blockchain.solana.tasks.transfer_to_user.batch_transfer_to_users',
            args=(owner_addresses, amounts)
        )
        self.logger.info("Sent batch transfer to users task to the queue")
        return task.get()


    def get_balance(self, owner_address: str) -> int:
        # Get the balance of the given owner
        # Return the balance
        owner = Pubkey.from_string(owner_address)

        associated_token_account_pubkey = spl_token.get_associated_token_address(
            owner,
            self.awe_mint_public_key,
            TOKEN_2022_PROGRAM_ID
        )

        resp = self.http_client.get_token_account_balance(
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
        return settings.solana_system_payer_public_key

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
            delegate=self.system_payer_public_key,
            owner=user_wallet_pk,
            amount=int(amount * 1e9),
            decimals=9
        )

        ix = spl_token.approve_checked(params)

        recent_blockhash = self.http_client.get_latest_blockhash().value.blockhash
        msg = Message.new_with_blockhash([ix], user_wallet_pk, recent_blockhash)

        tx = Transaction.new_unsigned(msg)
        return bytes(tx)


    def collect_user_payment(self, user_deposit_id: int, user_wallet: str, agent_creator_wallet: str, amount: int, game_pool_division: int) -> str:
        # Transfer tokens from the user wallet to the pool, agent creators and developers
        # Return the transaction hash
        task = app.send_task(
            name='awe.blockchain.solana.tasks.collect_user_fund.collect_user_fund',
            args=(user_deposit_id, user_wallet, agent_creator_wallet, amount, game_pool_division)
        )
        self.logger.info("Sent collect user payment task to the queue")
        return task.get()

    def collect_game_pool_charge(self,  charge_id: int, agent_creator_wallet: str, amount: int) -> str:
        task = app.send_task(
            name='awe.blockchain.solana.tasks.collect_user_fund.collect_game_pool_charge',
            args=(charge_id, agent_creator_wallet, amount)
        )

        self.logger.info("Sent collect game pool charge task to the queue")
        return task.get()


    def collect_user_staking(self, user_staking_id:int, user_wallet: str, amount: int) -> str:
        # Transfer tokens from the user wallet to the system wallet
        # Return the transaction hash
        task = app.send_task(
            name='awe.blockchain.solana.tasks.collect_user_fund.collect_user_staking',
            args=(user_staking_id, user_wallet, amount)
        )
        self.logger.info("Sent collect user staking task to the queue")
        return task.get()

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


    def get_awe_circulating_supply(self) -> float:
        cir_supply_resp = self.http_client.get_token_supply(self.awe_mint_public_key)
        return cir_supply_resp.value.ui_amount
