import json
import os
import traceback
from contextlib import AsyncExitStack
from datetime import datetime
from typing import Optional

from mcp import ClientSession
from mcp.client.sse import sse_client
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionToolParam

from configs.logging import logger
from configs.settings import OPENAI_API_KEY


class OpenAI_MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.llm = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self.tools = []
        self.messages = []
        self.init_message_with_prompt()
        self.logger = logger

    def init_message_with_prompt(self):
        system_prompt = {
            "role": "system",
            "content": """
                You are an assistant that uses tools to answer programming questions.
                You are allowed to use the tool 'get_docs' to fetch library documentation.
                Important: You MUST call the 'get_docs' tool at most ONCE per user message. 
                If the user mentions multiple libraries, choose the single most relevant one and fetch only that. 
                Explain clearly if more than one is needed, but do not call the tool multiple times.
            """,
        }
        self.messages.append(system_prompt)

    # connect to MCP server
    async def connect_to_server(self, server_url: str):
        try:
            # sse_client와 ClientSession을 async with로 안전하게 열고 닫음
            async with sse_client(url=server_url) as streams:
                async with ClientSession(*streams) as session:
                    self.session = session
                    await self.session.initialize()
                    self.logger.info("Connected to MCP server successfully.")

                    mcp_tools = await self.get_mcp_tools()
                    self.tools = [
                        ChatCompletionToolParam(
                            type="function",
                            function={
                                "name": tool.name,
                                "description": tool.description or "",
                                "parameters": tool.inputSchema,
                            },
                        )
                        for tool in mcp_tools
                    ]
                    self.logger.info(
                        f"Successfully connected to server. Available tools: {[tool['function']['name'] for tool in self.tools]}"
                    )
                    # 연결 성공 상태를 유지하기 위해 필요하면 self._streams_context, self._session_context 저장
                    # 또는 session 객체만 저장 후 외부에서 종료 관리

                    # 성공하면 True 리턴
                    return True

        except Exception as e:
            self.logger.error(f"Failed to connect to server: {str(e)}")
            self.logger.debug(f"Connection error details: {traceback.format_exc()}")
            return False


    # get mcp tool list
    async def get_mcp_tools(self):
        if not self.session:
            raise RuntimeError("Not connected to MCP server. Call connect_to_server first.")
        try:
            self.logger.info("Requesting MCP tools from the server.")
            response = await self.session.list_tools()
            return response.tools
        except Exception as e:
            self.logger.error(f"Failed to get MCP tools: {str(e)}")
            self.logger.debug(f"Error details: {traceback.format_exc()}")
            raise Exception(f"Failed to get tools: {str(e)}")

    # process chat message
    async def process_chat_message(self, message: str):
        if not self.session:
            raise RuntimeError("Not connected to MCP server. Call connect_to_server first.")
        try:
            self.logger.info(f"Processing chat message: {message}")
            user_message = {"role": "user", "content": message}
            self.messages.append(user_message)
            await self.log_conversation(self.messages)
            messages = [user_message]

            while True:
                self.logger.info("Calling OpenAI API")
                response = await self.call_llm()

                choice_message = response.choices[0].message
                self.logger.info(f"Received response: {choice_message}")

                if getattr(choice_message, "tool_calls", None):
                    assistant_message = {
                        "role": "assistant",
                        "content": (choice_message.content),
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments,
                                },
                                "type": tool_call.type,
                            }
                            for tool_call in choice_message.tool_calls  # type: ignore
                        ],
                    }
                    self.messages.append(assistant_message)
                    await self.log_conversation(self.messages)
                    messages.append(assistant_message)

                    # Tool 호출 처리
                    for tool_call in choice_message.tool_calls:  # type: ignore
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)
                        tool_use_id = tool_call.id

                        self.logger.info(
                            f"Executing tool: {tool_name} with args: {tool_args}"
                        )
                        try:
                            if self.session is None:
                                break

                            result = await self.session.call_tool(tool_name, tool_args)
                            self.logger.info(f"Tool result: {result}")

                            tool_result_message = {
                                "role": "tool",
                                "tool_call_id": tool_use_id,
                                "content": (result.content),
                            }
                            self.messages.append(tool_result_message)
                            await self.log_conversation(self.messages)
                            messages.append(tool_result_message)
                        except Exception as e:
                            error_msg = f"Tool execution failed: {str(e)}"
                            self.logger.error(error_msg)
                            raise Exception(error_msg)
                else:
                    assistant_message = {
                        "role": "assistant",
                        "content": (choice_message.content),
                    }
                    self.messages.append(assistant_message)
                    await self.log_conversation(self.messages)
                    messages.append(assistant_message)
                    break

            return messages
        except Exception as e:
            self.logger.error(f"Failed to process chat message: {str(e)}")
            self.logger.debug(f"Error details: {traceback.format_exc()}")
            raise Exception(f"Failed to process chat message: {str(e)}")

    # call llm
    async def call_llm(self):
        if not self.session:
            raise RuntimeError("Not connected to MCP server. Call connect_to_server first.")
        try:
            self.logger.info("Calling LLM with messages and tools.")
            response = await self.llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=self.messages,
                tools=self.tools,
                # tool_choice="auto",
                # stream=True,
            )
            return response
        except Exception as e:
            self.logger.error(f"Failed to call LLM: {str(e)}")
            self.logger.debug(f"Error details: {traceback.format_exc()}")
            raise Exception(f"Failed to call LLM: {str(e)}")

    # cleanup
    async def cleanup(self):
        try:
            await self.exit_stack.aclose()
            self.logger.info("Exited MCP client session successfully.")
        except Exception as e:
            self.logger.error(f"Failed to cleanup MCP client session: {str(e)}")
            self.logger.debug(f"Cleanup error details: {traceback.format_exc()}")
            raise Exception(f"Failed to cleanup session: {str(e)}")

    # log conversation
    async def log_conversation(self, conversation: list):
        """Log the conversation to json file"""
        # Create conversations directory if it doesn't exist
        os.makedirs("conversations", exist_ok=True)

        # Convert conversation to JSON-serializable format
        serializable_conversation = []
        for message in conversation:
            try:
                serializable_message = {"role": message["role"], "content": []}

                # Handle both string and list content
                if isinstance(message["content"], str):
                    serializable_message["content"] = message["content"]
                elif isinstance(message["content"], list):
                    for content_item in message["content"]:
                        if hasattr(content_item, "to_dict"):
                            serializable_message["content"].append(
                                content_item.to_dict()
                            )
                        elif hasattr(content_item, "dict"):
                            serializable_message["content"].append(content_item.dict())
                        elif hasattr(content_item, "model_dump"):
                            serializable_message["content"].append(
                                content_item.model_dump()
                            )
                        else:
                            serializable_message["content"].append(content_item)

                serializable_conversation.append(serializable_message)
            except Exception as e:
                self.logger.error(f"Error processing message: {str(e)}")
                self.logger.debug(f"Message content: {message}")
                raise

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = os.path.join("conversations", f"conversation_{timestamp}.json")

        try:
            with open(filepath, "w") as f:
                json.dump(serializable_conversation, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Error writing conversation to file: {str(e)}")
            self.logger.debug(f"Serializable conversation: {serializable_conversation}")
            raise
