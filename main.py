# HouseAI/main.py

# from fastapi import FastAPI
# from fastapi.responses import FileResponse
# import os

# app = FastAPI()

# # React의 public 폴더 경로 (index.html 위치)
# public_dir = os.path.join(os.path.dirname(__file__), "public")

# @app.get("/")
# def serve_index():
#     return FileResponse(os.path.join(public_dir, "index.html"))



# HouseAi/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from routers.user_router import router as user_router
from routers.list_router import router as list_router
import os

from routers.chat_router import router as chat_router

app = FastAPI()

# --- CORS 설정 (React 개발 서버와 연동) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

public_dir = os.path.join(os.path.dirname(__file__))

# --- API 라우터 등록 (HTML 라우트보다 먼저) ---
app.include_router(user_router)
app.include_router(chat_router)
app.include_router(list_router)

# --- SPA 라우팅: React Router 지원 ---
@app.get("/")
async def serve_index():
    """메인 페이지 서빙"""
    return FileResponse(os.path.join(public_dir, "index.html"))

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """
    React Router의 모든 경로를 index.html로 서빙
    /login, /signup, /dashboard 등 모든 프론트엔드 경로가 React Router로 처리됨
    """
    # API 경로는 제외 (이미 위에서 등록된 라우터들이 우선 처리됨)
    return FileResponse(os.path.join(public_dir, "index.html"))
