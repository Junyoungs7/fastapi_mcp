import httpx
from typing import Optional, Dict

async def fetch_chat_response(api_url: str, query: str, session_id: str) -> Optional[Dict]:
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{api_url}/chat", json={"message": query, "session_id": session_id})
            if response.status_code == 200:
                message = response.json()["messages"]

                return message
            else:
                return None
    except Exception as e:
        print(f"API 호출 에러: {e}")
        return None
