import streamlit as st
import httpx
from typing import Dict, Any

class Chatbot:
    def __init__(self, api_url: str):
        self.api_url = api_url
        if "messages" not in st.session_state:
            st.session_state["messages"] = []
        self.messages = st.session_state["messages"]

    def display_message(self, message: Dict[str, Any]):
        role = message["role"]

        # 4) assistant → 최종 답변
        if role == "assistant" and isinstance(message["content"], str):
            with st.chat_message(role):
                st.write(message["content"])
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
            if st.button("새 채팅"):
                st.session_state["messages"] = []

        query = st.chat_input("Ask a question")
        if query:
            st.session_state["messages"].append({"role": "user", "content": query})
            st.chat_message("user").markdown(query)

            with st.spinner("답변을 생성하는 중입니다"):
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{self.api_url}/chat", json={"message": query}
                    )
                    if response.status_code == 200:
                        message = response.json()["messages"]
                        st.session_state["messages"].append(message)

                        self.display_message(message)