import streamlit as st
from typing import Dict, Any
import http_client as client
import time
import uuid

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

        chat_list = await client.get_chat_list(self.api_url, 999)

        with st.sidebar:
            st.header("📜 채팅 내역")

            if st.button("✏️ 새 채팅"):
                st.session_state["messages"] = []
                st.session_state["session_id"] = str(uuid.uuid4())
                st.rerun()

            if chat_list:
                for chat in chat_list:
                    if st.button(chat.get("SESSION_ID")):
                        chat_id = chat["SESSION_ID"]
                        messages = await client.get_chat_messages(self.api_url, chat_id)

                        if messages:
                            st.session_state["messages"] = []
                            st.session_state["messages"] = messages
                            st.session_state["session_id"] = chat_id
                            st.rerun()

        # 세션 ID 없으면 초기화 (최초 접근 시)
        if "session_id" not in st.session_state:
            st.session_state["session_id"] = str(uuid.uuid4())

        if st.session_state["messages"]:
            for message in st.session_state["messages"]:
                self.display_message(message)

        query = st.chat_input("Ask a question")
        if query:
            st.session_state["messages"].append({"role": "user", "content": query})
            st.chat_message("user").markdown(query)

            with st.spinner("답변을 생성하는 중입니다"):
                session_id = st.session_state["session_id"]
                message = await client.fetch_chat_response(self.api_url, query, session_id)
                if message:
                    st.session_state["messages"].append(message)
                    with st.chat_message("assistant"):
                        def stream_text():
                            for char in message["content"]:
                                yield char
                                time.sleep(0.02)

                        st.write_stream(stream_text())
