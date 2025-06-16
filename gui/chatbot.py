import streamlit as st
from typing import Dict, Any
import http_client as client

class Chatbot:
    def __init__(self, api_url: str):
        self.api_url = api_url
        if "messages" not in st.session_state:
            st.session_state["messages"] = []
        self.messages = st.session_state["messages"]

    def display_message(self, message: Dict[str, Any]):
        role = message["role"]

        if role == "user" and isinstance(message["content"], str):
            st.chat_message("user").markdown(message["content"])
            return

        # assistant → 최종 답변
        if role == "assistant" and isinstance(message["content"], str):
            st.chat_message("assistant").markdown(message["content"])
            return

        # 예외 처리
        st.chat_message("assistant").write(f"_Unrecognized message format: {message}_")

    async def render(self):
        st.title("🤖 AI Chatbot")

        with st.sidebar:
            if st.button("✏️ 새 채팅"):
                st.session_state["messages"] = []

        if st.session_state["messages"]:
            for message in st.session_state["messages"]:
                self.display_message(message)

        query = st.chat_input("Ask a question")
        if query:
            st.session_state["messages"].append({"role": "user", "content": query})
            st.chat_message("user").markdown(query)

            with st.spinner("답변을 생성하는 중입니다"):
                message = await client.fetch_chat_response(self.api_url, query)
                if message:
                    st.session_state["messages"].append(message)
                    st.chat_message("assistant").markdown(message["content"])