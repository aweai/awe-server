from fastapi import APIRouter
from awe.blockchain import awe_on_chain

router = APIRouter(
    prefix="/v1/awe"
)

@router.get("/total-supply")
def awe_total_supply():
    return 1000000000.0

@router.get("/circulating-supply")
def awe_circulating_supply():
    return awe_on_chain.get_awe_circulating_supply()
