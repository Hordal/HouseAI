from pydantic import BaseModel

class WishCreate(BaseModel):
    house_id: str

class WishOut(BaseModel):
    user_id: int
    house_id: str

    class Config:
        from_attributes = True