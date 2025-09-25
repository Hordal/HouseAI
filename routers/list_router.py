from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from db.database import get_db
from schemas.list_schemas import WishCreate, WishOut
from services.list_services import add_wish, get_wishlist, delete_wish
from services.user_service import get_current_user

router = APIRouter(prefix="/wishlist", tags=["wishlist"])

@router.post("/add")
def add_to_wishlist(wish: WishCreate, authorization: str = Header(None), db: Session = Depends(get_db)):
    """JWT 토큰 기반으로 찜 목록에 매물 추가"""
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="인증 토큰이 필요합니다.")
        
        token = authorization.split(" ")[1]
        current_user = get_current_user(token, db)
        result = add_wish(db, current_user.user_id, wish.house_id)
        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")

@router.get("/")
def get_my_wishlist(authorization: str = Header(None), db: Session = Depends(get_db)):
    """JWT 토큰 기반으로 현재 사용자의 찜 목록 조회"""
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

@router.delete("/{house_id}")
def remove_from_wishlist(house_id: str, authorization: str = Header(None), db: Session = Depends(get_db)):
    """JWT 토큰 기반으로 찜 목록에서 매물 삭제"""
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="인증 토큰이 필요합니다.")
        
        token = authorization.split(" ")[1]
        current_user = get_current_user(token, db)
        result = delete_wish(db, current_user.user_id, house_id)
        if result["result"] == "success":
            return result
        raise HTTPException(status_code=404, detail=result["message"])
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")

# 기존 API들 (하위 호환성을 위해 유지)
@router.post("/", response_model=WishOut)
def add_to_wishlist_legacy(wish: WishCreate, user_id: int, db: Session = Depends(get_db)):
    try:
        return add_wish(db, user_id, wish.house_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/user/{user_id}")
def get_user_wishlist_legacy(user_id: int, db: Session = Depends(get_db)):
    return get_wishlist(db, user_id)