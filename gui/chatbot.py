import streamlit as st
import httpx
from typing import Dict, Any

class Chatbot:
    def __init__(self, api_url: str):
        self.api_url = api_url
        self.messages = st.session_state["messages"]

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
            
            
        # model = st.selectbox("Select AI Model", ["openai", "llama"])
        # user_input = st.text_input("You:", placeholder="Type your message here...")

        # if st.button("Send"):
        #     if user_input:
        #         response = await self.send_message(user_input, model)
        #         st.write(response)
        #     else:
        #         st.warning("Please enter a message before sending.")
