from .remote_llm import RemoteLLM
from .tools import RemoteSDTool, AweTransferTool, AweBalanceTool
from ..models.awe_agent import AweAgent as AgentConfig
from langchain.agents import create_json_chat_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_openai import ChatOpenAI
from langchain.callbacks.base import AsyncCallbackHandler
from typing import Dict, Any, List, Optional
from awe.models.user_agent_stats_invocations import UserAgentStatsInvocations, AITools
import asyncio

import logging
import traceback
import os

logger = logging.getLogger("[Awe Agent]")

supported_llm = ["local", "openai"]

llm_type = os.getenv("LLM", "")

if llm_type not in supported_llm:
    raise Exception("LLM type is not configured!")

if llm_type == "openai":
    key = os.getenv("OPENAI_API_KEY", "")
    if key == "":
        raise Exception("OpenAI API Key is not configured!")


class LLMInvocationLogHandler(AsyncCallbackHandler):
    """Async callback handler that can be used to handle callbacks from langchain."""

    def __init__(self, user_agent_id: int):
        super().__init__()
        self.user_agent_id = user_agent_id


    async def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], metadata: Optional[dict[str, Any]], **kwargs: Any
    ) -> None:

        if "tg_user_id" not in metadata:
            raise Exception("tg_user_id is not set")

        tg_user_id = metadata["tg_user_id"]

        # Log the invocation
        await asyncio.to_thread(UserAgentStatsInvocations.add_invocation, self.user_agent_id, tg_user_id, AITools.LLM)

    async def on_llm_end(self, response, *, run_id, parent_run_id = None, tags = None, **kwargs):

        if os.getenv("LOG_LEVEL", "") != "DEBUG":
            return

        logger.debug("Response from LLM")

        flattened_list = response.flatten()
        for flattened in flattened_list:
            logger.debug(flattened.llm_output)


class AweAgent:

    system_prompt="""

    The process to generate answer to the user input requires multiple steps that are represented by a markdown code snippet of a json blob.
    The json structure should contain the following keys:
    thought -> your thoughts
    action -> name of a tool
    action_input -> parameters to send to the tool

    These are the tools you can use: {tool_names}.

    These are the tools descriptions:

    {tools}

    If no tools are required to answer the question, use the tool "Final Answer" to give the text answer directly. Its parameters is the solution.
    If there is not enough information, try to give the final answer at your best knowledge.
    """

    human_prompt="""
    Add the word "STOP" after each markdown snippet. Example:

    ```json
    {{"thought": "<your thoughts>",
    "action": "<tool name or Final Answer to give a final answer>",
    "action_input": "<tool parameters or the final output"}}
    ```
    STOP

    This is my query="{input}". Write only the next step needed to solve it.
    Your answer should be based in the previous tools executions, even if you think you know the answer.
    Remember to add STOP after each snippet.

    These were the previous steps given to solve this query and the information you already gathered:
    """

    def __init__(self, user_agent_id: int, config: AgentConfig) -> None:

        llm_log_handler = LLMInvocationLogHandler(user_agent_id)

        verbose_output = os.getenv("LOG_LEVEL", "") == "DEBUG"

        if llm_type == "local":
            llm = RemoteLLM(
                llm_config=config.llm_config,
                callbacks=[llm_log_handler]
            )
        elif llm_type == "openai":
            model = os.getenv("OPENAI_MODEL", "gpt-4o")
            temp = float(os.getenv("OPENAI_TEMPERATURE", 0.7))
            max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", 300))
            max_retries = int(os.getenv("OPENAI_MAX_RETRIES", 2))
            timeout = int(os.getenv("LLM_TASK_TIMEOUT", 60))

            llm = ChatOpenAI(
                model=model,
                temperature=temp,
                max_tokens=max_tokens,
                timeout=timeout,
                max_retries=max_retries,
                callbacks=[llm_log_handler],
                verbose=verbose_output,
                disable_streaming=True
            )

        tools = []

        if config.image_generation_enabled:
            tools.append(RemoteSDTool(task_args=config.image_generation_args, user_agent_id=user_agent_id))

        if config.awe_token_enabled:
            tools.append(AweTransferTool(awe_token_config=config.awe_token_config, user_agent_id=user_agent_id))
            tools.append(AweBalanceTool(awe_token_config=config.awe_token_config, user_agent_id=user_agent_id))

        self.config = config

        prompt_template = self._build_prompt_template(config.llm_config.prompt_preset)

        agent = create_json_chat_agent(
            tools=tools,
            llm = llm,
            prompt = prompt_template,
            stop_sequence=["STOP"],
            template_tool_response="{observation}"
        )

        timeout = os.getenv("AGENT_RESPONSE_TIMEOUT", 100)
        timeout = int(timeout)

        handle_parsing_errors = int(os.getenv("AGENT_HANDLE_PARSING_ERRORS", 1)) == 1

        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=verbose_output,
            handle_parsing_errors=handle_parsing_errors,
            max_execution_time=timeout,
            max_iterations=5
        )

        self.history_memories = {}

        self.history_executor = RunnableWithMessageHistory(
            self.agent_executor,
            lambda session_id: self._get_memory_for_session(session_id),
            input_messages_key="input",
            history_messages_key="chat_history"
        )

    def _get_memory_for_session(self, session_id: str):

        session_id = str(session_id)

        if session_id not in self.history_memories:
            self.history_memories[session_id] = ChatMessageHistory()
        return self.history_memories[session_id]

    def _build_prompt_template(self, agent_preset_prompt: str) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                ("system", agent_preset_prompt + self.system_prompt),
                MessagesPlaceholder("chat_history", optional=True),
                ("human", self.human_prompt),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )

    async def get_response(self, input: str, tg_user_id: str, session_id: str = None) -> dict:

        output = ""

        try:
            if session_id is not None:
                resp = await self.history_executor.ainvoke(
                    {"input": input},
                    config={"configurable": {"session_id": session_id}, 'metadata': {'tg_user_id': tg_user_id}}
                )
            else:
                resp = await self.agent_executor.ainvoke(
                    {"input": input},
                    config={'metadata': {'tg_user_id': tg_user_id}}
                )

            output = resp["output"]
        except Exception as e:
            logger.error(e)
            logger.error(traceback.format_exc())

        resp_dict = {
            "text": None,
            "image": None
        }

        if output.startswith("[image]"):
            resp_dict["image"] = output[7:]
        else:
            resp_dict["text"] = output

        return resp_dict
