import logging.handlers
from pydantic_settings import BaseSettings
from pydantic import model_validator, Field
import logging
import enum
from typing import Optional, Annotated, Tuple
from typing_extensions import Self
from solders.keypair import Keypair
import os

from dotenv import load_dotenv

env_file = "persisted_data/.env"

if os.path.exists(env_file):
    load_dotenv(env_file)
else:
    raise Exception(f"Env file not specified: {env_file}")

class LLMType(str, enum.Enum):
    OpenAI = "openai"
    Local = "local"

class SolanaNetwork(str, enum.Enum):
    Devnet = "devnet"
    Testnet = "testnet"
    Mainnet = "mainnet-beta"

solana_network_endpoints = {
    SolanaNetwork.Devnet: "https://api.devnet.solana.com",
    SolanaNetwork.Mainnet: "https://api.mainnet-beta.solana.com",
    SolanaNetwork.Testnet: "https://api.testnet.solana.com"
}

class AweSettings(BaseSettings):

    server_host: str = "https://api.aweai.fun"
    webui_host: str = "https://aweai.fun"

    api_rate_limit: str = "20/minute"

    log_level: str = 'INFO'
    log_dir: str = ""
    admin_token: str

    db_connection_string: str
    db_log_level: str = 'WARN'
    celery_broker_url: str
    celery_backend_url: str
    redis_cache: str

    solana_network: SolanaNetwork = SolanaNetwork.Devnet
    solana_network_endpoint: str = ""
    solana_tx_wait_timeout: int = 60

    solana_awe_metadata_address: str
    solana_awe_mint_address: str
    solana_awe_program_id: str

    solana_system_payer_public_key: Optional[str] = None

    # Only provide this in the offline signing machine
    # to send blockchain transactions
    solana_system_payer_private_key: Optional[str] = None

    # Developer account to collect developer fee
    solana_developer_wallet: str

    llm_type: LLMType = LLMType.Local
    llm_task_timeout: int = 60
    sd_task_timeout: int = 60
    agent_recursion_limit: int = 5
    max_history_messages: int = 20


    openai_model: str = "gpt-4o"
    openai_api_key: str = ""
    openai_temperature: float = 0.7
    openai_max_tokens: int = 300
    openai_max_retries: int = 2

    # Signing key used for communication encryption
    comm_ed25519_public_key: str
    comm_ed25519_private_key: str

    # Delete the env file on disk after loading
    remove_env_file: bool = True

    # Tokenomics
    tn_developer_share: Annotated[float, Field(default=0.01, gt=0, le=1)]
    tn_agent_staking_amount: Annotated[int, Field(default=100, gt=0)]
    tn_agent_staking_locking_days: Annotated[int, Field(default=30, ge=0)]
    tn_user_staking_locking_days: Annotated[int, Field(default=30, ge=0)]
    tn_emission_start: int
    tn_emission_interval_days: int = 7

    # System prompt
    prepend_prompt: Annotated[Optional[str], Field(default=None)] = None
    append_prompt: Annotated[Optional[str], Field(default=None)] = None

    # Langsmith
    langsmith_api_key: Annotated[Optional[str], Field(default=None)] = None
    langsmith_tracing: Annotated[bool, Field(default=None)] = False
    langsmith_endpoint: Annotated[Optional[str], Field(default=None)] = None
    langsmith_project: Annotated[Optional[str], Field(default=None)] = None

    # Coinmarketcap API
    cmc_api_key: str

    group_chat_history_length: int = 50

    min_player_payment_amount: int = 1000
    min_player_staking_amount: int = 1000
    min_player_deposit_amount: int = 10000
    min_player_withdraw_amount: int = 1000
    min_creator_withdraw_amount: int = 1000
    min_game_pool_charge_amount: int = 1000
    withdraw_tx_fee: int = 10
    max_messages_per_play: int = 100

    def tn_share_user_payment(self, game_pool_division: int, amount: int) -> Tuple[int, int, int]:

        # Developer division
        developer_share = int(amount * self.tn_developer_share)
        if developer_share == 0:
            developer_share = 1

        remaining = amount - developer_share

        # Creator division
        creator_share = int(remaining * (100 - game_pool_division) / 100)
        if game_pool_division != 100 and creator_share == 0:
            creator_share = 1

        # Pool division
        pool_share = remaining - creator_share

        if pool_share < 0:
            raise Exception("Payment amount too small for the pool!")

        return pool_share, creator_share, developer_share

    @model_validator(mode="after")
    def openai_api_key_exist(self) -> Self:
        if self.llm_type == LLMType.OpenAI and self.openai_api_key == "":
            raise ValueError("openai_api_key must be provided")
        return self

    @model_validator(mode="after")
    def set_solana_network(self) -> Self:
        if self.solana_network_endpoint == "":
            self.solana_network_endpoint = solana_network_endpoints[self.solana_network]
        return self

    @model_validator(mode="after")
    def check_system_payer_keys(self) -> Self:
        if self.solana_system_payer_private_key is None and self.solana_system_payer_public_key is None:
            raise ValueError("Either solana_system_payer_private_key or solana_system_payer_public_key must be set")

        if self.solana_system_payer_private_key is not None:
            kp = Keypair.from_base58_string(self.solana_system_payer_private_key)
            pk = str(kp.pubkey())
            print(f"System payer public key: {pk}")
            if self.solana_system_payer_public_key is not None and self.solana_system_payer_public_key != pk:
                raise ValueError("Mismatch solana_system_payer_private_key and solana_system_payer_public_key")
            else:
                self.solana_system_payer_public_key = pk

        return self


settings = AweSettings()

# Prevent deleting env file using env var

keep_env_file = os.getenv("AWE_KEEP_ENV_FILE", False)
if settings.remove_env_file and not keep_env_file:
    os.remove(env_file)


log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

handlers = [
    logging.StreamHandler()
]

if settings.log_dir != "":
    handlers.append(logging.handlers.TimedRotatingFileHandler(
        settings.log_dir,
        when='midnight',
        backupCount=30
    ))


logging.basicConfig(
    format=log_format,
    level=settings.log_level,
    handlers=handlers
)
