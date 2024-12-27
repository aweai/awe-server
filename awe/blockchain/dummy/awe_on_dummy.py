from ..awe_onchain import AweOnChain

class AweOnDummy(AweOnChain):
    def get_user_num_agents(self, address: str) -> int:
        return 1

    def validate_signature(self, public_key: str, message: str, signature: str) -> str | None:
        # Validate the signature and return the address
        # Return None if validation failed
        return "0xEDa8747bfe3396Aa37c937faF5BB97952cEf3bf2"

    def transfer_token(self, dest_owner_address: str, amount: int) -> str:
        # Transfer AWE from the system account to the given wallet address
        # Return the tx address
        return ""

    def get_balance(self, owner_address: str) -> int:
        # Get the balance of the given wallet address
        # Return the balance
        return 0

    def get_system_payer(self) -> str:
        # Get the address of the system account
        return "0xEDa8747bfe3396Aa37c937faF5BB97952cEf3bf2"

    def is_valid_address(self, address: str) -> bool:
        # Check the validity of the wallet address
        return True

    def get_user_approve_transaction(self, user_wallet: str, amount: int) -> bytes:
        # Construct a tx for the user to approve the system account to transfer certain amount of tokens.
        return b""

    def collect_user_payment(self, user_wallet: str, amount: int) -> str:
        # Transfer tokens from the user wallet to the system wallet
        # Return the transaction hash
        return ""

    def wait_for_tx_confirmation(self, tx_hash: str, timeout: int):
        # Wait for the confirmation of the given tx
        # Or timeout
        pass
