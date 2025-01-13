from .remote_llm import RemoteLLM
from .tools import RemoteSDTool, AweTransferTool, AweAgentBalanceTool
from ..models.awe_agent import AweAgent as AgentConfig
from langchain_openai import ChatOpenAI
from langchain_core.runnables.config import RunnableConfig
from typing import Dict, Any, List, Optional, TypedDict, Annotated, Literal, Union
from awe.models.user_agent_stats_invocations import UserAgentStatsInvocations, AITools
from awe.settings import settings, LLMType
import asyncio
import logging
import traceback
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import AnyMessage
from pydantic import BaseModel

logger = logging.getLogger("[Awe Agent]")

class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]


class AweAgent:

    def __init__(self, user_agent_id: int, config: AgentConfig) -> None:

        self.config = config
        self.user_agent_id = user_agent_id

        verbose_output = settings.log_level == "DEBUG"

        if settings.llm_type == LLMType.Local:
            self.llm = RemoteLLM(
                llm_config=config.llm_config
            )
        elif settings.llm_type == LLMType.OpenAI:
            self.llm = ChatOpenAI(
                model=settings.openai_model,
                temperature=settings.openai_temperature,
                max_tokens=settings.openai_max_tokens,
                timeout=settings.llm_task_timeout,
                max_retries=settings.openai_max_retries,
                verbose=verbose_output,
                disable_streaming=True
            )

        tools = []

        if config.image_generation_enabled:
            tools.append(RemoteSDTool(task_args=config.image_generation_args, user_agent_id=user_agent_id))

        if config.awe_token_enabled:
            tools.append(AweTransferTool(awe_token_config=config.awe_token_config, user_agent_id=user_agent_id))
            tools.append(AweAgentBalanceTool(awe_token_config=config.awe_token_config, user_agent_id=user_agent_id))

        self.llm_with_tools = self.llm.bind_tools(tools, parallel_tool_calls=False, strict=True)

        graph_builder = StateGraph(State)
        graph_builder.add_node("chatbot", self.chatbot)
        graph_builder.set_entry_point("chatbot")

        # Tools
        tool_node = ToolNode(tools=tools)
        graph_builder.add_node("tools", tool_node)

        graph_builder.add_conditional_edges(
            "chatbot",
            tools_condition,
        )

        graph_builder.add_conditional_edges(
            "tools",
            self.terminate_tools_condition
        )

        # History
        memory = MemorySaver()

        self.graph = graph_builder.compile(checkpointer=memory)
        
        if settings.log_level == "DEBUG":
            print(self.graph.get_graph().draw_ascii())


    async def chatbot(self, state: State, config: RunnableConfig):

        tg_user_id = config.get("configurable", {}).get("tg_user_id")

        # Log the invocation
        await asyncio.to_thread(UserAgentStatsInvocations.add_invocation, self.user_agent_id, tg_user_id, AITools.LLM)

        message = await self.llm_with_tools.ainvoke(state["messages"])

        return {"messages": [message]}


    def terminate_tools_condition(
            self,
            state: Union[list[AnyMessage], dict[str, Any], BaseModel]
        ) -> Literal["chatbot", "__end__"]:

        if isinstance(state, list):
            tool_message = state[-1]
        elif isinstance(state, dict) and (messages := state.get("messages", [])):
            tool_message = messages[-1]
        elif messages := getattr(state, "messages", []):
            tool_message = messages[-1]
        else:
            raise ValueError(f"No messages found in input state to terminate_tools_condition: {state}")

        if hasattr(tool_message, "name"):

            tool_name = tool_message.name

            if tool_name in ["TransferAweToken", "GenerateImage"]:
                return "__end__"

        # Tool call failed. Return the message to agent
        return "chatbot"


    async def get_response(self, input: str, tg_user_id: str, thread_id: str = None) -> dict:

        output = ""

        try:
            if thread_id is not None:
                resp = await self.graph.ainvoke(
                    {"messages": [("user", input)]},
                    config={
                        "configurable": {"thread_id": thread_id, "tg_user_id": tg_user_id},
                        "recursion_limit": settings.agent_recursion_limit
                    },
                    debug=settings.log_level == "DEBUG"
                )
            else:
                resp = await self.graph.ainvoke(
                    {"messages": [("user", input)]},
                    config={'configurable': {'tg_user_id': tg_user_id}, "recursion_limit": settings.agent_recursion_limit},
                    debug=settings.log_level == "DEBUG"
                )

            logger.debug("response from graph ainvoke")
            logger.debug(resp)

            output = ""

            if 'messages' in resp:
                if len(resp["messages"]) > 0:
                    output = resp["messages"][-1].content          

            
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
