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
                You are an AI assistant that can only respond by using the provided tools. 
                Do not attempt to answer questions outside the scope of the tools. Do not generate general or free-form answers.
                If a user's query cannot be answered using the available tools, respond with:
                "죄송합니다. 해당 요청은 제공된 도구만으로는 처리할 수 없습니다."
            """,
        }
        self.messages.append(system_prompt)

    # connect to MCP server
    async def connect_to_server(self, server_url: str):
        try:
            self._streams_context = sse_client(url=server_url)
            streams = await self._streams_context.__aenter__()

            self._session_context = ClientSession(*streams)
            self.session = await self._session_context.__aenter__()

            await self.session.initialize()

            mcp_tools = await self.get_mcp_tools()
            self.tools = [
                ChatCompletionToolParam(
                    type="function",
                    function={
                        "name": tool.name,
                        "description": (
                            tool.description if tool.description is not None else ""
                        ),
                        "parameters": tool.inputSchema,
                    },
                )
                for tool in mcp_tools
            ]
            self.logger.info(
                f"Successfully connected to server. Available tools: {[tool['function']['name'] for tool in self.tools]}"
            )

            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to server: {str(e)}")
            self.logger.debug(f"Connection error details: {traceback.format_exc()}")
            raise Exception(f"Failed to connect to server: {str(e)}")


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
