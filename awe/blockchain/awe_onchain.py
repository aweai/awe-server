
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger("[AweOnChain]")

class AweOnChain(ABC):
# The general interfaces Awe needs to interact with a Blockchain
    @abstractmethod
    def get_user_num_agents(self, address: str) -> int:
        pass

    @abstractmethod
    def validate_signature(self, public_key: str, message: str, signature: str) -> str | None:
        # Validate the signature and return the address
        # Return None if validation failed
        pass

    @abstractmethod
    def transfer_to_user(self, dest_owner_address: str, amount: int) -> str:
        # Transfer AWE from the system account to the given wallet address
        # Return the tx address
        pass

    @abstractmethod
    def get_balance(self, owner_address: str) -> int:
        # Get the balance of the given wallet address
        # Return the balance
        pass

    @abstractmethod
    def get_system_payer(self) -> str:
        # Get the address of the system account
        pass

    @abstractmethod
    def is_valid_address(self, address: str) -> bool:
        # Check the validity of the wallet address
        pass

    @abstractmethod
    def get_user_approve_transaction(self, user_wallet: str, amount: int) -> bytes:
        # Construct a tx for the user to approve the system account to transfer certain amount of tokens.
        pass

    @abstractmethod
    def collect_user_payment(self, user_wallet: str, agent_creator_wallet: str, amount: int) -> str:
        # Transfer tokens from the user wallet to the system wallet
        # 69% to the pool (system wallet)
        # 30% to the agent creator
        # 1% to the developer
        # Return the transaction hash
        pass

    @abstractmethod
    def collect_user_staking(self, user_wallet: str, amount: int) -> str:
        # Transfer tokens from the user wallet to the system wallet
        # 69% to the pool (system wallet)
        # 30% to the agent creator
        # 1% to the developer
        # Return the transaction hash
        pass

    @abstractmethod
    def wait_for_tx_confirmation(self, tx_hash: str, timeout: int):
        # Wait for the confirmation of the given tx
        # Or timeout
        pass

    def token_ui_amount(self, amount: int) -> str:
        # Get the UI display for the given token amount
        int_part = int(int(amount) / int(1e9))
        decimal_part = f"{int(amount / int(1e7)) % 100}"
        if(len(decimal_part) == 1):
            decimal_part = f"0{decimal_part}"

        return f"AWE {int_part}.{decimal_part}"
