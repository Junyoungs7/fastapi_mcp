from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings

from mcp_client import OpenAI_MCPClient
from models.chat_request import ChatRequest

load_dotenv()


class Settings(BaseSettings):
    server_script_path: str = "http://localhost:8001/sse"


settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = OpenAI_MCPClient()
    try:
        connected = await client.connect_to_server(settings.server_script_path)
        if not connected:
            raise HTTPException(
                status_code=500, detail="Failed to connect to MCP server"
            )
        app.state.client = client
        yield
    except Exception as e:
        print(f"Error during lifespan {e}")
        raise e
    finally:
        # shutdown
        await client.cleanup()


app = FastAPI(title="VGT MCP Client", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to your needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"message": "i'm alive!"}


@app.post("/chat")
async def process_query(request: ChatRequest):
    """Process a query and return the response"""

    try:
        messages = await app.state.client.process_chat_message(request.message)
        return {"messages": messages}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tools")
async def get_tools():
    """Get the list of available tools"""
    try:
        tools = await app.state.client.get_mcp_tools()
        return {
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                }
                for tool in tools
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
