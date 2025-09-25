from fastapi import APIRouter, Depends, HTTPException, status, Body, Header
from sqlalchemy.orm import Session
from db.database import get_db, User
from schemas.user import UserCreate, UserLogin, UserOut
from services.user_service import (
    create_user, authenticate_user,
    create_access_token, create_refresh_token, verify_token, get_current_user
)
from services.list_services import get_wishlist
import db.database

router = APIRouter()

# 회원가입
@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    try:
        if db.query(User).filter_by(email=user_data.email).first():
            raise HTTPException(status_code=400, detail="이미 등록된 이메일입니다.")
        if not user_data.terms_agreed:
            raise HTTPException(status_code=400, detail="약관 동의가 필요합니다.")
        user = create_user(db, user_data.name, user_data.email, user_data.password, user_data.terms_agreed)
        return user
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")

# 로그인 (JWT 토큰 발급)
@router.post("/login")
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter_by(email=user_data.email).first()
        if not user:
            raise HTTPException(status_code=404, detail="이메일이 존재하지 않습니다.")
        if not authenticate_user(db, user_data.email, user_data.password):
            raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")
        access_token = create_access_token({"sub": user.email})
        refresh_token = create_refresh_token({"sub": user.email})
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "user_id": user.user_id,
                "name": user.name,
                "email": user.email,
                "terms_agreed": user.terms_agreed
            }
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")
# 리프레시 토큰으로 액세스 토큰 재발급
@router.post("/token/refresh")
def refresh_token(refresh_token: str = Body(...)):
    try:
        payload = verify_token(refresh_token, token_type="refresh")
        if not payload:
            raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다.")
        access_token = create_access_token({"sub": payload["sub"]})
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")

# 사용자 찜 목록 조회 (토큰 기반)
@router.get("/wishlist")
def get_current_user_wishlist(authorization: str = Header(None), db: Session = Depends(get_db)):
    """현재 로그인한 사용자의 찜 목록 조회"""
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="인증 토큰이 필요합니다.")
        
        token = authorization.split(" ")[1]
        current_user = get_current_user(token, db)
        result = get_wishlist(db, current_user.user_id)
        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")

# 사용자 찜 목록 조회 (기존 - 특정 user_id)
@router.get("/user/{user_id}/wishlist")
def get_user_wishlist(user_id: int, db: Session = Depends(get_db)):
    try:
        result = get_wishlist(db, user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")