from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings

from mcp_client import OpenAI_MCPClient
from models.chat_request import ChatRequest

load_dotenv()


class Settings(BaseSettings):
    server_script_path: str = "http://localhost:8080/sse"


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
    """Process a query and return the final assistant response only"""
    try:
        messages = await app.state.client.process_chat_message(request.message)
        final_response = None
        for message in reversed(messages):
            if message.get("role") == "assistant":
                final_response = message
                break

        if final_response is None:
            final_response = {"role": "assistant", "content": "죄송합니다. 정보를 제공해줄 수 없습니다."}

        return {"messages": final_response}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
