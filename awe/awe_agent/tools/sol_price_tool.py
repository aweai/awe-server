from langchain.tools import BaseTool
import asyncio
import requests
from awe.settings import settings
import logging

logger = logging.getLogger("[SOL Price Tool]")

class SolPriceTool(BaseTool):
    name: str = "SolPriceNow"
    description: str =  (
        "Get the current price of Solana Token (Token symbol is SOL or $SOL)"
    )

    def get_sol_price(self) -> str:

        resp = requests.get(
            "https://pro-api.coinmarketcap.com/v2/tools/price-conversion",
            params={
                "symbol": "SOL",
                "convert": "USD",
                "amount": 1
            },
            headers={
                "Accepts": "application/json",
                "X-CMC_PRO_API_KEY":settings.cmc_api_key
            }
        )

        if resp.status_code != 200:
            logger.error(f"[{resp.status_code}] {resp.text}")
            raise Exception("HTTP request failed!")

        data = resp.json()

        if "data" in data:
            if "quote" in data["data"]:
                if "USD" in data["data"]["quote"]:
                    return data["data"]["quote"]["USD"]["price"]


    async def _arun(self) -> str:
        return asyncio.to_thread(self.get_sol_price)


    def _run(self, _: str) -> str:
        raise Exception("Sync call should never be used")
