from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers.v1 import user_agents, admin, agent_stats, tg_phantom_wallets, user_wallets, agents, awe, emission
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from awe.settings import settings

app = FastAPI(redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


limiter = Limiter(key_func=get_remote_address, default_limits=[settings.api_rate_limit])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


app.include_router(user_agents.router)
app.include_router(admin.router)
app.include_router(agent_stats.router)
app.include_router(tg_phantom_wallets.router)
app.include_router(user_wallets.router)
app.include_router(agents.router)
app.include_router(awe.router)
app.include_router(emission.router)


# Agent PFPs
app.mount("/pfps", StaticFiles(directory="persisted_data/pfps"), name="agent_pfps")
