import streamlit as st
import httpx
import json
from typing import Dict, Any


class Chatbot:
    def __init__(self, api_url: str):
        self.api_url = api_url
        if "messages" not in st.session_state:
            st.session_state["messages"] = []
        self.messages = st.session_state["messages"]

    def display_message(self, message: Dict[str, Any]):
        role = message["role"]

        # 1) 사용자 텍스트
        if role == "user" and isinstance(message["content"], str):
            st.chat_message("user").markdown(message["content"])
            return

        # 2) assistant → tool_calls 요청
        if role == "assistant" and isinstance(message.get("tool_calls"), list):
            for call in message["tool_calls"]:
                func = call["function"]["name"]
                args = json.loads(call["function"]["arguments"])
                with st.chat_message("assistant"):
                    st.write(f"🛠️ Calling tool **{func}** with args:")
                    st.json(args)
            return

        # 3) tool → tool 결과
        if role == "tool" and isinstance(message["content"], list):
            with st.chat_message("assistant"):
                st.write(f"✅ Tool result (call_id={message.get('tool_call_id')}):")
                for chunk in message["content"]:
                    if chunk.get("type") == "text":
                        st.markdown(chunk["text"])
            return

        # 4) assistant → 최종 답변
        if role == "assistant" and isinstance(message["content"], str):
            st.chat_message("assistant").markdown(message["content"])
            return

        # (옵션) 예외 처리
        st.chat_message("assistant").write(f"_Unrecognized message format: {message}_")

    async def send_message(self, message: str, model: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/chat",
                json={"message": message, "model": model}
            )
            return response.json()

    async def get_tools(self) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.api_url}/tools")
            return response.json()

    async def render(self):
        st.title("AI Chatbot")

        with st.sidebar:
            st.subheader("Settings")
            st.write("API URL:", self.api_url)
            result = await self.get_tools()
            st.subheader("Available Tools")
            st.write([tool["name"] for tool in result.get("tools", [])])

        # 채팅 메시지 출력 영역

        message = st.chat_input("Ask a question")
        if message:
            # 사용자 메시지를 바로 session_state에 추가
            st.session_state["messages"].append({"role": "user", "content": message})

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.api_url}/chat", json={"message": message}
                )
                if response.status_code == 200:
                    messages = response.json()["messages"]
                    st.session_state["messages"] = messages

                    # 응답 메시지들 다시 출력
                    for message in messages:
                        self.display_message(message)



        # model = st.selectbox("Select AI Model", ["openai", "llama"])
        # user_input = st.text_input("You:", placeholder="Type your message here...")

        # if st.button("Send"):
        #     if user_input:
        #         response = await self.send_message(user_input, model)
        #         st.write(response)
        #     else:
        #         st.warning("Please enter a message before sending.")
