from dbconnection.diablo import db_manager as db
from datetime import datetime

async def insert_mcp_conversation(session_id: str, emp_code: str, emp_message: str, ai_message: str):
    print("emp_message", emp_message)

    query = "INSERT INTO dbo.TMP_MCP_CONVERSATION(SESSION_ID, EMP_CODE, EMP_MESSAGE, AI_MESSAGE, NEW_DATE) VALUES (?, ?, ?, ?, ?)"
    params = (session_id, emp_code, emp_message, ai_message, datetime.now())
    results = db.execute_write_query(query, params)
    return results

async def get_chat_list(emp_code: str):
    query = """
        SELECT SESSION_ID, MIN(NEW_DATE) AS NEW_DATE
        FROM dbo.TMP_MCP_CONVERSATION
        WHERE EMP_CODE = ?
        GROUP BY SESSION_ID
        ORDER BY NEW_DATE DESC
    """
    params = (emp_code,)
    results = db.execute_query(query, params)
    return results
