import os
import requests
import xmltodict
import json
from dotenv import load_dotenv
from pymongo import MongoClient
from math import radians, cos, sin, asin, sqrt
from openai import OpenAI

# --- 환경 설정 ---
load_dotenv()
SERVICE_KEY = os.getenv("SERVICE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI2", "mongodb://localhost:27017")
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")

# OpenAI 클라이언트 초기화 (새로운 방식)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# --- MongoDB 연결 (에러 핸들링 추가) ---
try:
    client = MongoClient(MONGO_URI)
    # 연결 테스트
    client.admin.command('ping')
    print("✅ MongoDB 연결 성공")
    db = client["real_estate"]
    apt_coll = db["apt_rent_seocho"]
    station_coll = db["subway_stations"]
    station_docs = list(station_coll.find({}, {"_id": 0}))
    print(f"📊 지하철역 데이터 로드: {len(station_docs)}개")
except Exception as e:
    print(f"❌ MongoDB 연결 실패: {e}")
    print(f"📝 MONGO_URI: {MONGO_URI}")
    exit(1)

# --- 위경도 거리 계산 ---
def haversine(lat1, lng1, lat2, lng2):
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng/2)**2
    return 2 * R * asin(sqrt(a))

# --- 가장 가까운 역 찾기 ---
def find_nearest_station(lat, lng, station_list):
    min_dist, nearest_station = float("inf"), None
    for st in station_list:
        d = haversine(lat, lng, st["lat"], st["lng"])
        if d < min_dist:
            min_dist = d
            nearest_station = st
    return nearest_station, min_dist

# --- 개선된 위경도 변환 ---
def get_coords_from_kakao(gu, dong, jibun, apt_name=None):
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    
    # 다양한 검색어 시도 (정확도 순)
    queries = []
    
    # 1. 아파트명 + 동 조합
    if apt_name:
        queries.append(f"서울특별시 {gu} {dong} {apt_name}")
        queries.append(f"서울 {gu} {apt_name}")
    
    # 2. 지번 주소 조합
    queries.append(f"서울특별시 {gu} {dong} {jibun}")
    queries.append(f"서울 {gu} {dong} {jibun}")
    
    # 3. 동 주소만
    queries.append(f"서울특별시 {gu} {dong}")
    
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    
    for query in queries:
        try:
            res = requests.get(url, headers=headers, params={"query": query.strip()})
            data = res.json()
            
            if data.get("documents"):
                result = data["documents"][0]
                lat = float(result["y"])
                lng = float(result["x"])
                print(f"✅ [좌표 변환 성공] '{query}' -> ({lat:.6f}, {lng:.6f})")
                return lat, lng
        except Exception:
            continue
    
    print(f"❌ [좌표 변환 실패] dong: '{dong}', jibun: '{jibun}', apt: '{apt_name}'")
    return None, None

# --- API 요청 ---
def fetch_apt_rent_data(lawd_cd, deal_ymd, page_no=1, num_of_rows=100):
    url = "http://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"
    params = {
        "serviceKey": SERVICE_KEY,
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": deal_ymd,
        "pageNo": page_no,
        "numOfRows": num_of_rows
    }
    response = requests.get(url, params=params)
    try:
        return json.loads(json.dumps(xmltodict.parse(response.content)))
    except Exception as e:
        print("❌ XML 파싱 오류:", e)
        return None

# --- 숫자 파싱 ---
def parse_int(value):
    try:
        return int(str(value).replace(",", "").strip())
    except:
        return 0

def parse_float(value):
    try:
        return float(str(value).replace(",", "").strip())
    except:
        return None

# --- 임베딩 문장 생성 ---
def generate_simple_text(gu, dong, apt, deposit, rent, area_pyeong, rent_type, floor, station_name=None, distance_m=None):
    parts = [gu, dong, apt]
    
    # 전세/월세에 따른 가격 정보 추가
    if rent_type == "전세":
        parts.append(f"전세 {deposit}만원")
    else:  # 월세
        parts.append(f"보증금 {deposit}만원")
        if rent:
            parts.append(f"월세 {rent}만원")
    
    # 면적 정보
    if area_pyeong:
        parts.append(f"{area_pyeong}평")
    
    # 층수 정보
    if floor:
        parts.append(f"{floor}층")
    
    # 역세권 정보
    if station_name and distance_m:
        minutes = round(distance_m / 70)
        parts.append(f"역세권 {station_name} 도보 {minutes}분")
    
    return " ".join(parts)

# --- 임베딩 생성 ---
def get_embedding(text):
    try:
        response = openai_client.embeddings.create(
            input=[text],
            model="text-embedding-3-small"
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"❌ 임베딩 오류: {e}")
        return None

# --- 실행 ---
if __name__ == "__main__":
    lawd_cd = "11650"  # 서초구
    deal_ymd = "202405"

    print("📦 서초구 전월세 실거래 수집 시작")
    
    # 기존 데이터 삭제 (안전하게 처리)
    try:
        delete_result = apt_coll.delete_many({})
        print(f"🧹 기존 문서 삭제 완료: {delete_result.deleted_count}건")
    except Exception as e:
        print(f"❌ 기존 데이터 삭제 실패: {e}")
        exit(1)
    
    total_saved = 0

    # API 데이터 확인
    first = fetch_apt_rent_data(lawd_cd, deal_ymd)
    if not first:
        print("❌ API 데이터 가져오기 실패")
        exit(1)
        
    total_count = int(first["response"]["body"]["totalCount"])
    print(f"📊 총 거래 건수: {total_count}건, 총 페이지 수: {(total_count // 100) + 1}")

    for page in range(1, (total_count // 100) + 2):
        print(f"📡 Page {page} 수집 중...")
        data = fetch_apt_rent_data(lawd_cd, deal_ymd, page_no=page)
        try:
            items = data["response"]["body"]["items"]["item"]
            if not isinstance(items, list):
                items = [items]
        except Exception as e:
            print(f"⚠️ 응답 파싱 오류: {e}")
            continue

        for item in items:
            dong = item.get("umdNm", "").strip()
            apt = item.get("aptNm", "").strip()
            jibun = item.get("jibun", "").strip()
            deposit = parse_int(item.get("deposit", ""))
            rent = parse_int(item.get("monthlyRent", ""))
            floor = str(item.get("floor", "")).strip()
            area_sqm = parse_float(item.get("excluUseAr", ""))
            area_pyeong = round(area_sqm * 0.3025, 2) if area_sqm else None
            rent_type = "전세" if rent == 0 else "월세"

            # 필수 필드 확인
            if not dong or not apt:
                print(f"❌ [필드 누락] dong: '{dong}', apt: '{apt}'")
                continue

            # 개선된 좌표 변환 (아파트명 포함)
            lat, lng = get_coords_from_kakao("서초구", dong, jibun, apt)
            if not lat or not lng:
                print(f"❌ [좌표 변환 실패] dong: '{dong}', apt: '{apt}' - 건너뛰기")
                continue

            # 가장 가까운 지하철역 찾기
            nearest_station, distance_m = find_nearest_station(lat, lng, station_docs)
            station_name = nearest_station["station_name"] if nearest_station else None

            text = generate_simple_text("서초구", dong, apt, deposit, rent, area_pyeong, rent_type, floor, station_name, distance_m)
            embedding = get_embedding(text)
            if not embedding:
                print(f"❌ [임베딩 실패] text: '{text}'")
                continue

            metadata = {
                "text": text,
                "gu": "서초구",
                "dong": dong,
                "jibun": jibun,
                "aptNm": apt,
                "floor": floor,
                "area_pyeong": area_pyeong,
                "deposit": deposit,
                "monthlyRent": rent,
                "rent_type": rent_type,
                "isAvailable": True,
                "lat": lat,
                "lng": lng,
                "nearest_station": station_name,
                "distance_to_station": distance_m
            }

            try:
                apt_coll.insert_one({
                    "embedding": embedding,
                    "metadata": metadata
                })
                total_saved += 1
                print(f"✅ 저장 완료: {text}")
            except Exception as e:
                print(f"❌ 저장 실패: {text} / Error: {e}")
                continue

    print(f"\n🎉 전체 저장 완료: {total_saved}건")
