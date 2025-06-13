import streamlit as st
import requests

st.set_page_config(page_title="chatVGT", page_icon=":robot_face:", layout="wide")
st.title("AI Chatbot")

model = st.selectbox("select AI Model", ["openai", "llama"])

user_input = st.text_input("You:", placeholder="이곳에 메시지를 작성해주세요...")

if st.button("Send"):
    if user_input:
        response = requests.post(
            "http://localhost:8000/chat",
            json={"message": user_input, "model": model}
        ).json()
        st.write(response)
    else:
        st.warning("Please enter a message before sending.")
