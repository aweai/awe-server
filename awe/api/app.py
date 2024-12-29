from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers.v1 import user_agents, admin, agent_stats, tg_phantom_wallets, user_wallets
from fastapi.staticfiles import StaticFiles


app = FastAPI(redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(user_agents.router)
app.include_router(admin.router)
app.include_router(agent_stats.router)
app.include_router(tg_phantom_wallets.router)
app.include_router(user_wallets.router)


# Agent PFPs
app.mount("/pfps", StaticFiles(directory="persisted_data/pfps"), name="agent_pfps")
