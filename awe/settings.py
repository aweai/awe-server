from pydantic_settings import BaseSettings
from pydantic import model_validator, Field
import logging
import enum
from typing import Optional

from dotenv import load_dotenv
load_dotenv("persisted_data/.env")

class LLMType(enum.Enum):
    OpenAI = "openai"
    Local = "local"

class SolanaNetwork(enum.Enum):
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
    log_level: str = 'INFO'
    admin_token: str

    db_connection_string: str
    celery_broker_url: str
    celery_backend_url: str
    redis_cache: str

    solana_network: SolanaNetwork = SolanaNetwork.Devnet
    solana_network_endpoint: str = solana_network_endpoints[SolanaNetwork.Devnet]

    solana_awe_metadata_address: str
    solana_awe_mint_address: str
    solana_awe_program_id: str

    solana_system_payer_public_key: str

    # Only provide this in the offline signing machine
    # to send blockchain transactions
    solana_system_payer_private_key: Optional[str]

    llm_type: LLMType = LLMType.Local
    agent_response_timeout: int = 100
    llm_task_timeout: int = 60
    sd_task_timeout: int = 60
    agent_handle_parsing_errors: bool = True

    openai_model: str = "gpt-4o"
    openai_api_key: str = ""
    openai_temperature: float = 0.7
    openai_max_tokens: int = 300
    openai_max_retries: int = 2

    # Signing key used for communication encryption
    comm_ed25519_public_key: str
    comm_ed25519_private_key: str

    @model_validator(mode="after")
    def openai_api_key_exist(self) -> str:
        if self.llm_type == LLMType.OpenAI and self.openai_api_key == "":
            raise ValueError("openai_api_key must be provided")

    @model_validator(mode="after")
    def set_solana_network(self):
        self.solana_network_endpoint = solana_network_endpoints[self.solana_network]


settings = AweSettings()

log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

logging.basicConfig(
    format=log_format,
    level=settings.log_level
)
