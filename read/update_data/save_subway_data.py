import csv
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 1. CSV 불러오기 (pandas 대신 표준 라이브러리 사용)
def read_subway_csv(filename):
    subway_data = []
    try:
        with open(filename, 'r', encoding='euc-kr') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # 컬럼명 매핑
                station_data = {
                    "line": row.get("호선", ""),
                    "station_name": row.get("역명", ""),
                    "lat": float(row.get("위도", 0)) if row.get("위도") else None,
                    "lng": float(row.get("경도", 0)) if row.get("경도") else None
                }
                # 유효한 데이터만 추가
                if station_data["station_name"] and station_data["lat"] and station_data["lng"]:
                    subway_data.append(station_data)
        return subway_data
    except FileNotFoundError:
        print(f"❌ 파일을 찾을 수 없습니다: {filename}")
        return []
    except Exception as e:
        print(f"❌ CSV 읽기 오류: {e}")
        return []

# 2. MongoDB 연결
MONGO_URI = os.getenv("MONGO_URI2", "mongodb://localhost:27017")

# MongoDB 연결 (에러 핸들링 추가)
try:
    client = MongoClient(MONGO_URI)
    # 연결 테스트
    client.admin.command('ping')
    print("✅ MongoDB 연결 성공")
    db = client["real_estate"]
    collection = db["subway_stations"]
except Exception as e:
    print(f"❌ MongoDB 연결 실패: {e}")
    print(f"📝 MONGO_URI: {MONGO_URI}")
    exit(1)

# 3. CSV 데이터 읽기
print("📡 CSV 파일 읽는 중...")

# 현재 스크립트 위치를 기준으로 CSV 파일 경로 설정
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_filename = "서울교통공사_1_8호선 역사 좌표(위경도) 정보_20241031.csv"
csv_path = os.path.join(script_dir, csv_filename)

print(f"📁 스크립트 위치: {script_dir}")
print(f"📄 CSV 파일 경로: {csv_path}")
print(f"📋 파일 존재 여부: {os.path.exists(csv_path)}")

# 현재 디렉토리의 파일 목록 출력
print("📂 현재 디렉토리 파일 목록:")
for file in os.listdir(script_dir):
    if file.endswith('.csv'):
        print(f"  - {file}")

subway_data = read_subway_csv(csv_path)

if not subway_data:
    print("❌ CSV 데이터를 읽을 수 없습니다.")
    exit(1)

print(f"📊 읽어온 지하철역 데이터: {len(subway_data)}개")

# 4. 기존 데이터 삭제 및 새 데이터 삽입
try:
    delete_result = collection.delete_many({})
    print(f"🧹 기존 데이터 삭제: {delete_result.deleted_count}개")
    
    insert_result = collection.insert_many(subway_data)
    print(f"✅ 새 데이터 저장: {len(insert_result.inserted_ids)}개")
    
    print("✅ 지하철 좌표 데이터를 MongoDB에 저장 완료")
    
    # 저장된 데이터 샘플 출력
    sample = collection.find_one()
    if sample:
        print(f"📝 저장된 데이터 샘플: {sample}")
        
except Exception as e:
    print(f"❌ 데이터 저장 실패: {e}")
    exit(1)
