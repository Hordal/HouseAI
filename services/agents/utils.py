"""
Utility functions for Multi-Agent Chat Service
공통 유틸리티 함수들
"""

import time
import logging
from typing import Dict, List, Any, Optional
from functools import wraps
from openai import OpenAI
import os
import re
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import ServerSelectionTimeoutError


# 캐싱 시스템 (우선순위 2)
_cache = {}
_cache_timestamps = {}
CACHE_EXPIRY = 300  # 5분

# 성능 모니터링용 로거 (우선순위 2)
class MultiAgentLogger:
    def __init__(self):
        self.logger = logging.getLogger("MultiAgentSystem")
        self.logger.setLevel(logging.INFO)
        
        # 파일 핸들러 추가
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def log_agent_start(self, agent_name: str, task_type: str, query: str):
        """에이전트 작업 시작 로깅"""
        self.logger.info(f"🚀 {agent_name} 시작 - {task_type}: '{query[:50]}...'")
    
    def log_agent_end(self, agent_name: str, task_type: str, duration: float, success: bool):
        """에이전트 작업 완료 로깅"""
        status = "✅" if success else "❌"
        self.logger.info(f"{status} {agent_name} 완료 - {task_type} ({duration:.2f}초)")
    
    def log_error(self, agent_name: str, error: Exception, context: Dict[str, Any]):
        """에러 로깅"""
        self.logger.error(f"💥 {agent_name} 오류: {str(error)} | 컨텍스트: {context}")
    
    def info(self, message: str):
        """일반 정보 로깅"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """경고 로깅"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """에러 로깅"""
        self.logger.error(message)

# 전역 로거 인스턴스
multi_agent_logger = MultiAgentLogger()

# OpenAI 클라이언트 싱글톤 (우선순위 1)
_openai_client = None

def get_openai_client() -> OpenAI:
    """OpenAI 클라이언트 싱글톤"""
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client

def cache_result(key: str, data: Any, expiry: int = CACHE_EXPIRY):
    """결과 캐싱 (우선순위 2)"""
    _cache[key] = data
    _cache_timestamps[key] = time.time() + expiry

def get_cached_result(key: str) -> Optional[Any]:
    """캐시된 결과 조회 (우선순위 2)"""
    if key in _cache:
        if time.time() < _cache_timestamps[key]:
            return _cache[key]
        else:
            # 만료된 캐시 제거
            del _cache[key]
            del _cache_timestamps[key]
    return None

def clear_expired_cache():
    """만료된 캐시 정리 (우선순위 2)"""
    current_time = time.time()
    expired_keys = [
        key for key, expiry_time in _cache_timestamps.items()
        if current_time >= expiry_time
    ]
    for key in expired_keys:
        del _cache[key]
        del _cache_timestamps[key]

def get_cache_stats() -> Dict[str, Any]:
    """캐시 통계 반환 (우선순위 2)"""
    clear_expired_cache()
    return {
        "total_cached_items": len(_cache),
        "cache_keys": list(_cache.keys())
    }

def safe_str(val: Any) -> str:
    """값을 안전하게 문자열로 변환"""
    try:
        if val is None:
            return ""
        return str(val).strip()
    except:
        return ""

def safe_float(val: Any) -> float:
    """값을 안전하게 실수로 변환"""
    try:
        if isinstance(val, str):
            return float(val.replace(",", "").strip())
        return float(val)
    except:
        return 0.0


def safe_int(val: Any) -> int:
    """문자열이나 숫자를 안전하게 정수로 변환"""
    try:
        if isinstance(val, str):
            # 콤마 제거 후 정수 변환
            return int(val.replace(",", "").strip())
        return int(val)
    except:
        return 0


def format_korean_price(amount: int) -> str:
    """한국 단위로 가격 포맷팅 (만원 -> 억 만원)"""
    if amount == 0:
        return "0원"
    
    # 억 단위 계산
    eok = amount // 10000
    man = amount % 10000
    
    if eok > 0:
        if man > 0:
            return f"{eok}억 {man:,}만원"
        else:
            return f"{eok}억"
    else:
        return f"{amount:,}만원"


def add_rent_type_info(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """검색 결과에 전세/월세 구분 정보를 추가"""
    enhanced_results = []
    
    for result in results:
        # 기존 결과 복사
        enhanced_result = result.copy()
        
        # monthlyRent와 deposit 값 추출
        monthly_rent = safe_int(result.get("monthlyRent", 0))
        deposit = safe_int(result.get("deposit", 0))
        
        if monthly_rent == 0:
            # 전세인 경우
            enhanced_result["rent_type_display"] = "전세"
            enhanced_result["price_display"] = f"전세 {format_korean_price(deposit)}" if deposit > 0 else "전세"
        else:
            # 월세인 경우
            enhanced_result["rent_type_display"] = "월세"
            # 월세는 보통 100만원 미만이므로 만원 단위로만 표시
            monthly_rent_formatted = f"{monthly_rent:,}만원" if monthly_rent > 0 else "0만원"
            enhanced_result["price_display"] = f"보증금 {format_korean_price(deposit)}/월세 {monthly_rent_formatted}"
        
        enhanced_results.append(enhanced_result)
    
    return enhanced_results

def calculate_price_per_py(property_dict):
    """
    평당가(1평=3.3㎡)를 계산하여 반환합니다. 가격(만원), 면적(㎡)이 있어야 합니다.
    """
    try:
        deposit = float(property_dict.get("deposit", 0))
        area_pyeong = float(property_dict.get("area_pyeong", 0))
        if area_pyeong <= 0:
            return None
        py = area_pyeong / 3.3
        return round(deposit / py, 2)
    except Exception:
        return None

def calculate_price_value(property_dict):
    """
    매물의 가격 가치를 계산합니다. (면적 / 평당가)
    """
    try:
        deposit = float(property_dict.get("deposit", 0))
        area_pyeong = float(property_dict.get("area_pyeong", 0))
        if area_pyeong <= 0 or deposit <= 0:
            return 0
        price_per_py = deposit / area_pyeong
        if price_per_py <= 0:
            return 0
        return round(area_pyeong / price_per_py, 2)
    except Exception:
        return 0

def validate_fields(property_dict):
    """
    필수 필드(가격, 면적 등)가 있는지 확인합니다. 없으면 ValueError 발생.
    """
    required = ["price", "area"]
    for field in required:
        if field not in property_dict:
            raise ValueError(f"필수 필드 누락: {field}")

def get_average_property(properties: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    매물 리스트에서 주요 수치의 평균값을 계산해 하나의 매물(dict) 형태로 반환 (평당가, 가격가치 포함)
    - deposit, monthlyRent, area_pyeong, distance_to_station, price_per_py, price_value
    """
    if not properties:
        return {}
    keys = ["deposit", "monthlyRent", "area_pyeong", "distance_to_station"]
    avg_property = {}
    for key in keys:
        values = [float(p.get(key, 0)) for p in properties if key in p]
        avg_property[key] = round(sum(values) / len(values), 2) if values else 0

    # 평당가(만원) 평균
    price_per_py_list = []
    for p in properties:
        try:
            deposit = float(p.get("deposit", 0))
            area = float(p.get("area_pyeong", 0))
            if area > 0:
                price_per_py_list.append(deposit / area)
        except Exception:
            continue
    avg_property["price_per_py"] = round(sum(price_per_py_list) / len(price_per_py_list), 2) if price_per_py_list else 0

    # 가격가치(예: 면적/평당가) 평균 (서비스 기준에 맞게 조정 가능)
    price_value_list = []
    for p in properties:
        try:
            deposit = float(p.get("deposit", 0))
            area = float(p.get("area_pyeong", 0))
            if area > 0:
                price_per_py = deposit / area
                if price_per_py > 0:
                    price_value_list.append(area / price_per_py)
        except Exception:
            continue
    avg_property["price_value"] = round(sum(price_value_list) / len(price_value_list), 2) if price_value_list else 0

    avg_property["aptNm"] = "평균 매물"
    avg_property["rent_type"] = "N/A"
    return avg_property

def extract_location_from_query(query: str) -> Optional[str]:
    # '동', '역', '구' 추출 (가장 앞에 나오는 것 우선)
    m = re.search(r'([가-힣]+(동|역|구))', query)
    if m:
        return m.group(1)
    return None

def resolve_references(query: str, history: List[Dict]) -> List[Dict]:
    references = []
    # 1. 동/역/구+숫자(들) 패턴 추출 (ex: 강남동 1번 2번, 신촌역 3번)
    loc_nums_pattern = re.findall(r'([가-힣]+(?:동|역|구))((?:\s*[0-9]+번)+)', query)
    # 2. 동/역/구 여러 개 + 숫자 여러 개 (ex: 강남동 신촌역 1번 2번)
    loc_list = re.findall(r'([가-힣]+(?:동|역|구))', query)
    num_list = re.findall(r'(?<![가-힣])([0-9]+)번', query)

    # 1. 동/역/구+숫자(들) 패턴이 있는 경우 (ex: 강남동 1번 2번 신촌역 3번)
    used_nums = set()
    if loc_nums_pattern:
        for loc, nums_str in loc_nums_pattern:
            nums = re.findall(r'([0-9]+)번', nums_str)
            for num in nums:
                used_nums.add((loc, num))
                for entry in reversed(history):
                    if entry.get("location") == loc:
                        props = entry["result"].get("results", [])
                        idx = int(num) - 1
                        if 0 <= idx < len(props):
                            references.append(props[idx])
                        break
        # 1번/2번 케이스에서 이미 매칭된 숫자는 중복 방지
        for num in num_list:
            if any(num == x[1] for x in used_nums):
                continue
            idx = int(num) - 1
            if history:
                props = history[-1]["result"].get("results", [])
                if 0 <= idx < len(props):
                    references.append(props[idx])
        return references

    # 2. 동/역/구 여러 개 + 숫자 여러 개 (순서대로 매칭, ex: 강남동 신촌역 1번 2번)
    if loc_list and num_list and len(loc_list) == len(num_list):
        for loc, num in zip(loc_list, num_list):
            for entry in reversed(history):
                if entry.get("location") == loc:
                    props = entry["result"].get("results", [])
                    idx = int(num) - 1
                    if 0 <= idx < len(props):
                        references.append(props[idx])
                    break
        return references

    # 2-1. 동/역/구 여러 개 + 숫자 하나 (ex: 강남동 신촌역 잠실구 2번)
    if loc_list and num_list and len(num_list) == 1 and len(loc_list) > 1:
        num = num_list[0]
        for loc in loc_list:
            for entry in reversed(history):
                if entry.get("location") == loc:
                    props = entry["result"].get("results", [])
                    idx = int(num) - 1
                    if 0 <= idx < len(props):
                        references.append(props[idx])
                    break
        return references

    # 4. 동/역/구와 숫자 개수가 다르더라도, 위에서 모두 처리하므로 에러 발생시키지 않음

    # 3. 숫자만 있는 경우 (ex: 1번 2번 3번)
    if not loc_list and num_list:
        for num in num_list:
            idx = int(num) - 1
            if history:
                props = history[-1]["result"].get("results", [])
                if 0 <= idx < len(props):
                    references.append(props[idx])
        return references

    # (아래 코드는 위에서 모두 처리되었으므로 중복 제거)

_mongo_client = None

def get_mongo_client() -> MongoClient:
    """
    MongoDB 클라이언트 싱글톤 객체를 반환합니다.

    환경 변수 `MONGO_URI`를 사용하여 연결을 설정하며, 최초 연결 시
    서버에 ping을 보내 연결 상태를 검증합니다. 연결 실패 시 오류를 발생시킵니다.
    """
    global _mongo_client
    if _mongo_client is None:
        mongo_uri = os.getenv("MONGO_URI", "").strip()
        if not mongo_uri:
            multi_agent_logger.error("MongoDB 연결 실패: MONGO_URI 환경 변수가 설정되지 않았습니다.")
            raise ValueError("MONGO_URI environment variable is required")

        try:
            multi_agent_logger.info("MongoDB에 연결을 시도합니다...")
            # search_agent.py의 안정적인 연결 설정을 참고하여 타임아웃 등 옵션 추가
            client = MongoClient(
                mongo_uri,
                tls=True, 
                connectTimeoutMS=10000,
                serverSelectionTimeoutMS=10000
            )
            # 서버에 ping을 보내 연결이 유효한지 검증
            client.admin.command("ping")
            _mongo_client = client
            multi_agent_logger.info("✅ MongoDB 연결 성공 및 검증 완료.")
        
        except ServerSelectionTimeoutError as e:
            multi_agent_logger.error(f"💥 MongoDB 연결 실패 (Timeout): {e}")
            raise
        except Exception as e:
            multi_agent_logger.error(f"💥 MongoDB 클라이언트 생성 중 알 수 없는 오류 발생: {e}")
            raise
            
    return _mongo_client

def get_mongodb_collection(
    collection_env_var: str = "APT_COLL", 
    db_env_var: str = "DB_NAME"
) -> Collection:
    """
    환경 변수에서 지정된 데이터베이스와 컬렉션에 대한 PyMongo Collection 객체를 가져옵니다.

    이 함수는 get_mongo_client()를 호출하여 중앙 관리되는 클라이언트를 사용합니다.

    Args:
        collection_env_var (str): 컬렉션 이름이 저장된 환경 변수의 이름. (기본값: "APT_COLL")
        db_env_var (str): 데이터베이스 이름이 저장된 환경 변수의 이름. (기본값: "DB_NAME")

    Returns:
        Collection: 요청된 PyMongo Collection 객체.
    
    Raises:
        ValueError: 필요한 환경 변수가 설정되지 않은 경우.
    """
    client = get_mongo_client()
    
    db_name = os.getenv(db_env_var, "real_estate").strip()
    collection_name = os.getenv(collection_env_var, "").strip()

    if not collection_name:
        error_msg = f"{collection_env_var} 환경 변수가 설정되지 않아 컬렉션을 가져올 수 없습니다."
        multi_agent_logger.error(error_msg)
        raise ValueError(error_msg)

    collection = client[db_name][collection_name]
    multi_agent_logger.info(f"MongoDB 컬렉션 '{db_name}.{collection_name}'을(를) 성공적으로 가져왔습니다.")
    return collection

