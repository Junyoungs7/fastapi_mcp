from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi import Query
from fastapi import Path

from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings

from mcp_client import OpenAI_MCPClient
from models.chat_request import ChatRequest

from dbconnection import diablo
from repositories import conversations_repository
import logging

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
    emp_info = "내 이름(emp_name)은 김준영이고, 사번(emp_code)은 2023243이며 부서명(team_name)은 IT개발팀입니다. 해당 정보를 바탕으로 요청에 답변해주세요."
    if request.message:
        request.message = f"{emp_info} {request.message}"
    try:
        messages = await app.state.client.process_chat_message(request.message)

        if not isinstance(messages, list):
            raise ValueError("응답 형식이 잘못되었습니다. 리스트가 아닙니다.")

        final_response = next(
            (m for m in reversed(messages) if m.get("role") == "assistant"),
            {"role": "assistant", "content": "죄송합니다. 정보를 제공해줄 수 없습니다."}
        )


        session_id = request.session_id
        try:
            await conversations_repository.insert_mcp_conversation(session_id, "999", request.message, final_response["content"])
        except Exception as db_error:
            logging.exception("DB 저장 중 오류 발생:")

        return {"messages": final_response}

    except Exception as e:
        logging.exception("처리 중 예외 발생:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/list")
async def get_chat_list(emp_code: str = Query(...)):
    try:
        chat_list = await conversations_repository.get_chat_list(emp_code)
        return {"chat_list": chat_list}
    except Exception as e:
        logging.exception("채팅 목록 조회 중 오류 발생:")
        raise HTTPException(status_code=500, detail="채팅 목록을 불러오는 중 오류가 발생했습니다.")



@app.get("/chat/{chat_id}/messages")
async def get_chat_messages_endpoint(chat_id: str = Path(...)):
    try:
        messages = await conversations_repository.get_chat_messages(chat_id)
        return {"chat_message_list": messages}
    except Exception as e:
        logging.exception("채팅 메시지 조회 중 오류 발생:")
        raise HTTPException(status_code=500, detail="채팅 메시지를 불러오는 중 오류가 발생했습니다.")



if __name__ == "__main__":
    import uvicorn

    diablo.init_db_connection()
    uvicorn.run(app, host="0.0.0.0", port=8001)
