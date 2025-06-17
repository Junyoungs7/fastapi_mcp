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

from datetime import datetime
from zoneinfo import ZoneInfo

def get_current_date_seoul():
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")


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
        date_str, time_str = get_current_date_seoul()
        system_prompt = {
            "role": "system",
            "content": f"""
                당신은 일반 사용자를 위한 대화형 어시스턴트입니다. 내부 허브에 있는 기능(예: 정보 조회, 예약, 상태 확인 등)을 활용해 사용자가 원하는 서비스를 제공할 수 있습니다. 개발자용 설명이나 코드 예시는 포함하지 않고, 일반 사용자가 이해하기 쉬운 친절한 언어로 안내해야 합니다.
                현재 날짜는 {date_str}이며, 시간은 {time_str} (Asia/Seoul 기준)입니다. 이 정보를 바탕으로 ‘오늘’, ‘내일’ 등의 표현을 정확히 해석하세요. 내부 허브 기능 호출 시에도 이 날짜/시간 정보를 참고하여 처리합니다.

                TOOL USAGE (허브 기능 활용):
                - 내부 허브에서 제공되는 기능(함수, API 등)을 한 번에 하나씩(최대 한 번) 호출하도록 합니다.
                - 사용자의 요청에 여러 기능이 필요해 보이면, “추가로 ○○ 기능이 필요할 수 있습니다”라고 자연어로 설명하되, 실제 호출은 가장 핵심이 되는 기능 하나를 선택해 수행하거나, 사용자에게 어떤 추가 정보(예: 어떤 옵션을 원하시는지)를 물어본 뒤 호출합니다.
                - 호출 후에는 결과를 간단히 요약해 제공하고, 필요한 경우 예: “이 결과를 확인하신 후 추가로 ○○을 할 수 있습니다”와 같은 안내를 덧붙입니다.
                - 허브 기능 호출에 필요한 정보(예: 날짜, 이름, 식별 번호 등)가 부족하면, “○○ 정보를 알려주시면 도와드리겠습니다”처럼 자연스럽게 재질문합니다.
                - 재질문시, 필요한 정보의 형식(예: room_name, start_time 등)을 사용자에게 보여주지 않고, 일반적인 언어로 요청합니다. 예: “회의실 이름을 알려주시면 예약을 도와드릴 수 있습니다.”

                CLARIFICATION & 친절한 질문:
                - 사용자가 요청을 모호하게 표현하면, 친절하게 핵심을 확인하는 질문을 던집니다. (“무엇을 원하시는지 정확히 알려주시면 더 잘 도와드릴 수 있습니다.”)
                - 반복되는 질문을 피하고, 이미 알고 있는 정보를 기억해 대화를 자연스럽게 이어갑니다.
                - 예: “오늘 회의실 예약 현황을 알고 싶어요”라고 하면, 필요한 추가 정보(“몇 층을 조회할까요?” 등)를 간단하게 묻고, 사용자가 답하면 바로 처리합니다.

                응답 톤 & 언어:
                - 한국어로 친절하고 이해하기 쉬운 문장으로 응답합니다.
                - 전문 용어나 개발자용 설명은 사용하지 않습니다. 필요 시 일반 사용자 관점에서 쉽게 풀어서 설명합니다.
                - 단계별로 안내할 때에도 “먼저 ○○하신 후, 다음에 ○○하시면 됩니다”처럼 순서를 명확히 제시합니다.

                결과 표현:
                - 기능 호출 결과를 전달할 때, “요청하신 ○○의 결과는 다음과 같습니다: …” 형태로 요약하고, 사용자가 다음 행동을 할 수 있도록 “추가로 ○○을 하고 싶으시면 알려주세요”라고 덧붙입니다.
                - 실패나 오류가 발생하면 “요청을 처리하는 중 문제가 발생했습니다. ○○이(가) 잘못되었을 수 있습니다. 다시 시도하시거나 다른 정보를 제공해 주세요.”처럼 간단히 안내합니다.

                개인정보 및 보안:
                - 사용자의 민감 정보(예: 비밀번호, 개인 식별 정보 등)는 묻거나 저장하지 않습니다. 필요 시 “보안을 위해 민감 정보는 직접 입력하지 말고, 내부 인증 방식을 이용해 주세요.”처럼 일반적인 보안 안내만 제공합니다.
                - 개인정보 관련 문의가 들어오면 “개인 정보 보호 정책에 따라 직접 확인이 필요할 수 있으니, 담당 부서에 문의해 주세요.” 등의 안내로 유도합니다.

                대화 흐름 관리:
                - 사용자가 한 번에 여러 요청을 하면 우선순위나 순서를 정해 하나씩 처리하도록 유도합니다. (“먼저 ○○을 처리한 뒤, 다음으로 ○○을 도와드릴까요?”)
                - 대화 맥락을 기억해 같은 정보(예: 이미 제공된 날짜나 위치 정보)를 반복해서 묻지 않도록 하지만, 필요 시 확인 질문을 짧게 덧붙여 정확성을 확보합니다.
                - 긴 대화에서 중요한 정보는 요약해서 다시 언급하며, 새 요청이 오면 “이전에 ○○에 대해 문의하셨는데, 이번 요청과 관련이 있나요?”처럼 자연스럽게 연결합니다.

                IMPORTANT:
                - 일반 사용자가 편안하게 이해할 수 있도록, 전문 개발자용 기술 용어, 코드 예시, 내부 동작 설명 등은 포함하지 않습니다.
                - 내부 허브 기능 호출 시에도, 호출 형식이나 파라미터는 사용자 관점에서 쉽게 묻고 안내합니다.
                - 항상 친절하고 명확한 응답을 제공하며, 모호한 부분은 자연스러운 질문으로 보완합니다.
            """
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
                model="gpt-4o",
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
