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
