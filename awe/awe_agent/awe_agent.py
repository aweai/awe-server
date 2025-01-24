from .remote_llm import RemoteLLM
from .tools import RemoteSDTool, AweTransferTool, AweAgentBalanceTool, RoundTimeTool, SolPriceTool, BatchAweTransferTool
from awe.models.user_agent import UserAgent as UserAgentConfig
from langchain_openai import ChatOpenAI
from langchain_core.runnables.config import RunnableConfig
from typing import Any, TypedDict, Annotated, Literal, Union
from awe.models.user_agent_stats_invocations import UserAgentStatsInvocations, AITools
from awe.settings import settings, LLMType
import asyncio
import logging
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages, Messages, RemoveMessage
from langchain_core.messages import trim_messages, SystemMessage, AnyMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel
import traceback


logger = logging.getLogger("[Awe Agent]")


def handle_message_update(left: Messages, right: Messages) -> Messages:
    merged = add_messages(left, right)

    trimmed = trim_messages(
        merged,
        max_tokens=settings.max_history_messages,
        token_counter=len,
        include_system=True
    )

    return trimmed


class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, handle_message_update]


class AweAgent:

    def __init__(self, user_agent_id: int, config: UserAgentConfig) -> None:

        self.user_agent = config
        self.config = config.awe_agent
        self.user_agent_id = user_agent_id

        verbose_output = settings.log_level == "DEBUG"

        if settings.llm_type == LLMType.Local:
            self.llm = RemoteLLM(
                llm_config=self.config.llm_config
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

        tools.append(RoundTimeTool(user_agent_id=user_agent_id))

        if self.config.image_generation_enabled:
            tools.append(RemoteSDTool(task_args=self.config.image_generation_args, user_agent_id=user_agent_id))

        if self.config.awe_token_enabled:
            tools.append(AweTransferTool(awe_token_config=self.config.awe_token_config, user_agent_id=user_agent_id))
            tools.append(BatchAweTransferTool(awe_token_config=self.config.awe_token_config, user_agent_id=user_agent_id))
            tools.append(AweAgentBalanceTool(awe_token_config=self.config.awe_token_config, user_agent_id=user_agent_id))
            tools.append(SolPriceTool())

        self.llm_with_tools = self.llm.bind_tools(tools, parallel_tool_calls=False, strict=True)

        graph_builder = StateGraph(State)
        graph_builder.add_node("chatbot", self.chatbot)
        graph_builder.set_entry_point("chatbot")

        # Tools
        tool_node = ToolNode(tools=tools)
        graph_builder.add_node("tools", tool_node)

        graph_builder.add_node("reset", self.reset_pre)
        graph_builder.add_edge("reset", "__end__")

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

    async def reset_pre(self, state: State, config: RunnableConfig):
        return []

    async def chatbot(self, state: State, config: RunnableConfig):

        tg_user_id = config.get("configurable", {}).get("tg_user_id")
        add_message_only = config.get("configurable", {}).get("add_message_only")

        if add_message_only:
            return {"messages": []}

        # Log the invocation
        await asyncio.to_thread(UserAgentStatsInvocations.add_invocation, self.user_agent_id, tg_user_id, AITools.LLM)

        if len(state["messages"]) == 1:
            logger.debug("Only 1 message. Add system prompt.")
            system_prompt = SystemMessage(self.get_system_prompt())
            user_message = state["messages"][-1]
            delete_message = RemoveMessage(id=user_message.id)
            new_user_message = HumanMessage(content=user_message.content)
            ai_message = await self.llm_with_tools.ainvoke([system_prompt, new_user_message])
            return {"messages": [delete_message, system_prompt, new_user_message, ai_message]}
        else:
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

            if tool_name in ["SingleTransferAweToken", "BatchTransferAweToken", "GenerateImage"]:
                return "__end__"

        # Tool call failed. Return the message to agent
        return "chatbot"


    async def clear_message_for_user(self, tg_user_id: str):
        config = {"configurable": {"thread_id": tg_user_id},}
        current_state = await self.graph.aget_state(config)
        messages = current_state.values["messages"]
        deleted_messages = [RemoveMessage(id=m.id) for m in messages]
        await self.graph.aupdate_state(config, {"messages": deleted_messages}, as_node="reset")


    def get_system_prompt(self) -> str:
        memegent_prompt = self.config.llm_config.prompt_preset

        chat_mode_prompt = "Players will interact will you in either private chat or group chat. The chat mode is the prefix of each message. Do not mention the chat mode, just respond accordingly."
        chat_mode_prompt += f"\nYour name is {self.user_agent.tg_bot.username} in the group chat"

        return f"{memegent_prompt}\n{chat_mode_prompt}"


    async def get_response(self, input: str, tg_user_id: str, thread_id: str) -> dict:

        output = ""

        try:
            resp = await self.graph.ainvoke(
                {"messages": [("user", input)]},
                config={
                    "configurable": {"thread_id": thread_id, "tg_user_id": tg_user_id, "add_message_only": False},
                    "recursion_limit": settings.agent_recursion_limit
                },
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


    async def add_message(self, message: str, tg_user_id: str, thread_id: str):
        try:
            await self.graph.ainvoke(
                {"messages": [("user", message)]},
                config={
                    "configurable": {"thread_id": thread_id, "tg_user_id": tg_user_id, "add_message_only": True},
                    "recursion_limit": settings.agent_recursion_limit
                },
                debug=settings.log_level == "DEBUG"
            )
        except Exception as e:
            logger.error(e)
            logger.error(traceback.format_exc())
