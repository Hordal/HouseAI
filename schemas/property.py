from pydantic import BaseModel
from typing import Optional

class PropertyItem(BaseModel):
    _id : str # ID 필드 
    gu: str
    dong: str
    jibun: str
    aptNm: str
    floor: str
    area_pyeong: str
    deposit: str
    monthlyRent: str
    rent_type: str
    nearest_station: str              
    distance_to_station: float             
    score: float
    lat: Optional[float] = None       # 위도
    lng: Optional[float] = None       # 경도
