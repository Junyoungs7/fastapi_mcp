import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="settings.env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MCP_SINGLE_SERVER_URL = os.getenv("MCP_SINGLE_SERVER_URL")
