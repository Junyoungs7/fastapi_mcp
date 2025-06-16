import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="settings.env")

SERVER = os.getenv("SERVER")
DATABASE = os.getenv("DATABASE")
UID = os.getenv("UID")
PWD = os.getenv("PWD")
