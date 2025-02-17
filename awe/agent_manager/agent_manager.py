from ..models.user_agent import UserAgent as UserAgentConfig
from .user_agent import UserAgent
import multiprocessing as mp
import time
import logging
import signal
from awe.db import engine, init_engine
from awe.cache import init_cache
from sqlmodel import Session, select


def start_user_agent(user_agent_config: UserAgentConfig):
    init_engine()
    init_cache()
    user_agent = UserAgent(user_agent_config)
    user_agent.start_tg_bot()


class AgentManager:
    def __init__(self) -> None:
        self.user_agent_processes = {}
        self.kill_now = False
        self.updated_at = -1
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        self.logger = logging.getLogger("[Agent Manager]")

    def load_user_agents(self) -> list[UserAgentConfig]:
        with Session(engine) as session:
            # Check if we already have this agent in the local db
            where = (UserAgentConfig.enabled==True) if self.updated_at == -1 else (UserAgentConfig.updated_at > self.updated_at)
            statement = select(UserAgentConfig).where(where).order_by(UserAgentConfig.updated_at.asc())
            user_agents = session.exec(statement).all()
            self.logger.debug(f"Loaded {len(user_agents)} agents")
            return user_agents

    def exit_gracefully(self, signum, frame):
        self.logger.info("Gracefully shutdown the agent manager in 30 seconds...")
        self.kill_now = True

    def start_agent_process(self, user_agent_config: UserAgentConfig):
        self.logger.debug(f"Starting user agent process: {user_agent_config.id} / {user_agent_config.user_address}")
        p = mp.Process(target=start_user_agent, args=(user_agent_config,))
        p.daemon = True
        p.start()
        self.user_agent_processes[user_agent_config.id] = p
        self.logger.info(f"User agent process started: {user_agent_config.id} / {user_agent_config.user_address}")

    def stop_agent_process(self, agent_id: int):
        self.logger.debug(f"Terminating user agent process: {agent_id}")
        if agent_id not in self.user_agent_processes:
            return
        p = self.user_agent_processes[agent_id]
        p.terminate()
        p.join()
        del self.user_agent_processes[agent_id]
        self.logger.info(f"User agent process terminated: {agent_id}")

    def restart_agent_process(self, user_agent_config: UserAgentConfig):
        self.stop_agent_process(user_agent_config.id)
        self.start_agent_process(user_agent_config)

    def run(self) -> None:

        self.logger.info("Agent manager starting...")

        first_time_start = True

        while(not self.kill_now):
            self.logger.debug("Checking for user agent updates...")
            updated_agents = self.load_user_agents()

            if first_time_start and len(updated_agents) == 0:
                self.logger.debug("First time starting...setting updated_at according to the time")
                self.updated_at = int(time.time()) - 30
            elif len(updated_agents) != 0:
                self.logger.debug("Setting updated_at according to the last updated agent")
                self.updated_at = updated_agents[len(updated_agents) - 1].updated_at

            for updated_agent in updated_agents:
                if updated_agent.enabled:
                    if first_time_start:
                        self.logger.debug(f"First time starting agent {updated_agent.id}")
                        self.start_agent_process(updated_agent)
                    else:
                        self.logger.debug(f"Restarting updated agent {updated_agent.id}")
                        self.restart_agent_process(updated_agent)
                else:
                    self.logger.debug(f"Stopping disabled updated agent {updated_agent.id}")
                    self.stop_agent_process(updated_agent.id)

            first_time_start = False
            self.logger.debug(f"Updated {len(updated_agents)} user agents")

            time.sleep(10)

        self.logger.info("Agent manager terminated!")
