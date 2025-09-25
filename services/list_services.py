from sqlalchemy.orm import Session
from db.database import WishList
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from bson import ObjectId

# .env에서 환경변수 불러오기
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

# MongoDB 연결 (Atlas 또는 환경에 맞게)
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client["real_estate"]
house_coll = mongo_db["apt_rent_seocho"]

def add_wish(db: Session, user_id: int, house_id: str):
    """찜 추가 (중복 방지)"""
    # 이미 찜한 매물인지 확인
    if db.query(WishList).filter_by(user_id=user_id, house_id=house_id).first():
        return {"result": "fail", "message": "이미 찜한 매물입니다."}
    # 찜 추가
    wish = WishList(user_id=user_id, house_id=house_id)
    db.add(wish)
    db.commit()
    return {"result": "success", "message": "찜 등록 성공"}

def get_wishlist(db: Session, user_id: int, limit: int = 20):
    """유저의 찜 목록을 MongoDB에서 상세 정보까지 반환"""
    # 1. SQL에서 찜한 house_id 목록 조회
    house_ids = [
        row.house_id for row in db.query(WishList)
        .filter_by(user_id=user_id)
        .limit(limit)
        .all()
    ]
    if not house_ids:
        # 찜한 매물이 없을 때
        return {"result": "fail", "message": "찜한 매물이 없습니다.", "data": []}

    # 2. house_id(ObjectId) 변환 (MongoDB용)
    object_ids = []
    for hid in house_ids:
        try:
            object_ids.append(ObjectId(hid))
        except Exception as e:
            print(f"[에러] house_id '{hid}' ObjectId 변환 실패: {e}")

    if not object_ids:
        # 유효한 매물 ID가 없을 때
        return {"result": "fail", "message": "유효한 매물 ID가 없습니다.", "data": []}

    # 3. MongoDB에서 상세 정보 조회
    try:
        houses = list(house_coll.find({"_id": {"$in": object_ids}}))
        meta_list = []
        for h in houses:
            meta = h.get("metadata", {})  # 매물의 메타데이터 추출
            meta["_id"] = str(h["_id"])   # ObjectId를 문자열로 변환
            meta_list.append(meta)
        if meta_list:
            # 매물 정보가 있을 때
            return {"result": "success", "data": meta_list}
        else:
            # MongoDB에서 매물 정보를 찾을 수 없을 때
            return {"result": "fail", "message": "찜한 매물이 없습니다.", "data": []}
    except Exception as e:
        # MongoDB 요청 실패 시
        return {"result": "fail", "message": f"MongoDB 요청 실패: {e}", "data": []}

def delete_wish(db: Session, user_id: int, house_id: str):
    """찜 삭제"""
    # 해당 찜이 존재하는지 확인
    wish = db.query(WishList).filter_by(user_id=user_id, house_id=house_id).first()
    if wish:
        db.delete(wish)
        db.commit()
        return {"result": "success", "message": "찜 삭제 성공"}
    # 찜 목록에 해당 매물이 없을 때
    return {"result": "fail", "message": "찜 목록에 해당 매물이 없습니다."}