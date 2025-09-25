from sqlalchemy import Column, Integer, String, ForeignKey
from db.database import Base

class WishList(Base):
    __tablename__ = "wishlist"
    user_id = Column(Integer, primary_key=True)  # PK, FK
    house_id = Column(String(64), nullable=False)
    # house_info 컬럼은 제거

    # user_id만 PK이므로 한 사용자당 한 매물만 찜 가능