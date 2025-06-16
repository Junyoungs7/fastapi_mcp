import streamlit as st
from chatbot import Chatbot

async def main():
    if "server_connected" not in st.session_state:
        st.session_state.server_connected = False
        
    if "tools" not in st.session_state:
        st.session_state["tools"] = []

    if "messages" not in st.session_state:
        st.session_state["messages"] = []
        
    API_URL = "http://localhost:8001"  # Replace with your actual API URL
    
    st.set_page_config(
        page_title="AI Chatbot",
        page_icon="🤖"
    )
    
    chatbot = Chatbot(API_URL)

    await chatbot.render()

import asyncio

if __name__ == "__main__":
    asyncio.run(main())
