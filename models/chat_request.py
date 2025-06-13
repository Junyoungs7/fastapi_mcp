from pydantic import BaseModel
from typing import Dict, Any


class ChatRequest(BaseModel):
    message: str


class Message(BaseModel):
    role: str
    content: Any


class ToolCall(BaseModel):
    name: str
    args: Dict[str, Any]
