
from fastapi import APIRouter, WebSocket
from fastapi.responses import JSONResponse
import os
import tempfile
from services.enhanced_multi_agent_service import enhanced_websocket_chat_handler

router = APIRouter()

@router.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    """Multi-Agent 채팅 (기존 엔드포인트에서 Multi-Agent 사용)"""
    await enhanced_websocket_chat_handler(ws)


# search_history.json 임시파일 삭제용 엔드포인트 (프론트 새로고침 시 호출)
@router.post("/api/reset_search_history")
async def reset_search_history():
    """search_history.json 임시파일 삭제 (프론트 새로고침 시 호출)"""
    temp_path = os.path.join(tempfile.gettempdir(), "search_history.json")
    print(f"[reset_search_history] 호출됨. 파일 경로: {temp_path}")
    try:
        if os.path.exists(temp_path):
            print(f"[reset_search_history] 파일 존재. 삭제 시도.")
            os.remove(temp_path)
            print(f"[reset_search_history] 파일 삭제 완료.")
            return JSONResponse(content={"result": "success", "message": "search_history.json 파일 삭제됨"})
        else:
            print(f"[reset_search_history] 파일이 존재하지 않음.")
            return JSONResponse(content={"result": "not_found", "message": "파일이 존재하지 않음"})
    except Exception as e:
        print(f"[reset_search_history] 삭제 중 오류: {e}")
        return JSONResponse(content={"result": "error", "message": str(e)}, status_code=500)
