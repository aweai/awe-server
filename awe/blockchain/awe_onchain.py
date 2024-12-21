
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
    def transfer_token(self, dest_owner_address: str, amount: int) -> str:
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

    def token_ui_amount(self, amount: int) -> str:
        # Get the UI display for the given token amount
        int_part = int(int(amount) / int(1e9))
        decimal_part = f"{int(amount / int(1e7)) % 100}"
        if(len(decimal_part) == 1):
            decimal_part = f"0{decimal_part}"

        return f"AWE {int_part}.{decimal_part}"
