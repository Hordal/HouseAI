from sqlalchemy import create_engine, Column, String, Boolean, Integer, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Base 선언 (한 번만)
Base = declarative_base()

# .env 파일에서 환경변수 불러오기
load_dotenv()

# 환경변수에서 값 읽기
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_DATABASE = os.getenv("DB_DATABASE")

DATABASE_URL = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3308/{DB_DATABASE}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# userdb 테이블 ORM 모델
class User(Base):
    __tablename__ = "userdb"
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    terms_agreed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=True)

# wishlist 테이블 ORM 모델
class WishList(Base):
    __tablename__ = "wishlist"
    user_id = Column(Integer, primary_key=True)  # PK, FK
    house_id = Column(String(64), primary_key=True, nullable=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()