"""
Search Agent for Multi-Agent Chat Service
부동산 매물 검색 전문 에이전트 (통합 버전)
"""

import os
import re
import logging
import time
import json
from typing import Dict, List, Any, Optional, Union
from collections import defaultdict

import numpy as np
import openai
from openai import OpenAI
from pydantic import BaseModel, Field
from pymongo import MongoClient, ReadPreference
from pymongo.errors import ServerSelectionTimeoutError
from .utils import get_mongodb_collection

# ------------------------
# 설정 및 로깅
# ------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("pymongo").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# 환경 변수 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")


# OpenAI 클라이언트 생성 (1.x 버전)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# MongoDB 컬렉션 로드
try:
    collection = get_mongodb_collection(collection_env_var="APT_COLL")
    subway_collection = get_mongodb_collection(collection_env_var="SUBWAY_COLL")
    logger.info("MongoDB 컬렉션 로드 성공")
except ValueError as e:
    logger.error(f"MongoDB 컬렉션 로드 실패: {e}")
    raise

# 상수
VECTOR_LIMIT = 60
TEXT_LIMIT = 60
VECTOR_WEIGHT = 0.3
TEXT_WEIGHT = 0.7
RANK_CONSTANT = 60

# --- OpenAI Tool Calling을 위한 Pydantic 스키마 정의 ---
class SearchParameters(BaseModel):
    """사용자 쿼리에서 추출된 부동산 검색 파라미터"""
    gu: Optional[str] = Field(None, description="검색할 자치구 이름 (예: 서초구, 강남구)")
    dong: Optional[str] = Field(None, description="검색할 동 이름 (예: 서초동, 방배동)")
    rent_type: Optional[str] = Field(None, description="임대 유형", pattern="^(전세|월세)$")
    max_deposit: Optional[int] = Field(None, description="보증금 상한선 (만원 단위)")
    max_monthly: Optional[int] = Field(None, description="월세 상한선 (만원 단위)")
    station_name: Optional[str] = Field(None, description="가까운 지하철역 이름 (예: 강남, 교대)")
    is_subway_search: bool = Field(False, description="사용자가 지하철역 근처를 명시적으로 검색했는지 여부")
    max_distance: int = Field(1000, description="지하철역으로부터의 최대 거리 (미터 단위)")


class SearchAgent:
    """부동산 매물 검색 전문 에이전트 (통합 버전)"""
    
    # 설정 상수들
    STATION_CORRECTIONS = {
        "교데역": "교대", "교대역": "교대", "강남역": "강남", "서초역": "서초",
        "방배역": "방배", "사당역": "사당", "양재역": "양재", "양재시민의숲역": "양재시민의숲",
        "남부터미널역": "남부터미널", "고속터미널역": "고속터미널", "내방역": "내방",
        "이수역": "이수", "동작역": "동작", "총신대입구역": "총신대입구", "반포역": "반포",
        "구반포역": "구반포", "잠원역": "잠원", "신반포역": "신반포", "논현역": "논현",
        "신논현역": "신논현", "언주역": "언주", "선정릉역": "선정릉", "한티역": "한티",
        "도곡역": "도곡", "매봉역": "매봉", "aT센터역": "aT센터"
    }
    
    DONG_TYPO_CORRECTIONS = {
        "서천동": "서초동", "서촌동": "서초동", "서초둥": "서초동", "서쵸동": "서초동",
        "잠원둥": "잠원동", "잠웡동": "잠원동", "반포둥": "반포동", "바포동": "반포동",
        "방배둥": "방배동", "방베동": "방배동", "양재둥": "양재동", "양제동": "양재동",
        "내곡둥": "내곡동", "내국동": "내국동"
    }
    
    GU_TYPO_CORRECTIONS = {
        "서촌구": "서초구", "서쵸구": "서초구", "서초귀": "서초구", "서초궁": "서초구",
        "서천구": "서초구", "서최구": "서초구", "서컴구": "서초구"
    }
    
    STATION_VARIATIONS = {
        "강남": ["강남"],
        "교대": ["교대"],
        "서초": ["서초"],
        "남부터미널": ["남부터미널"],
        "고속터미널": ["고속터미널"],
        "신논현": ["신논현"],
        "논현": ["논현"],
        "잠원": ["잠원"],
        "반포": ["반포"],
        "신반포": ["신반포"],
        "구반포": ["구반포"],
        "방배": ["방배"],
        "사당": ["사당"],
        "양재": ["양재"]
    }
    
    def __init__(self):
        self.system_prompt = """
        너는 AI 기반 부동산 매물 검색 전문 Agent야.
        사용자의 자연어 질문을 이해하고, 그 의도에 맞는 검색 조건을 정확히 추출해야 한다.
        """
        
        self.intelligent_correction_prompt = """
        너는 AI 기반 지명 오타 교정 및 의도 파악 전문가야.
        
        고급 교정 능력:
        1. 발음 유사성 분석 (예: "서촌" → "서초")
        2. 타이핑 오류 패턴 (예: "ㅊ" ↔ "ㅈ" 오타)
        3. 줄임말/속어 인식 (예: "강남역" → "강남")
        4. 컨텍스트 기반 추론 (예: 주변 키워드로 의도 파악)
        5. 지역 인접성 고려 (예: 인근 구/동 추천)
        
        규칙:
        1. 가장 확신도 높은 후보 1개만 선택
        2. 확신도 70% 미만이면 "없음" 응답
        3. 사용자 의도를 반영한 스마트 교정
        4. 후보 목록 외 추천 금지
        5. 교정 근거나 설명 없이 결과만
        
        향상된 예시:
        - "서촌구" + 후보: ["서초구", "서대문구"] → "서초구" (발음 유사성)
        - "간남역" + 후보: ["강남", "강서"] → "강남" (타이핑 오류)
        - "고터역" + 후보: ["고속터미널", "교대"] → "고속터미널" (줄임말)
        """
        # 사용 가능한 구들 로드
        self.available_gus = self._get_available_gus()

    def search_properties(self, query: str, top_k: int = 30) -> Dict[str, Any]:
        """하이브리드 검색을 수행하고 결과를 사전 형태로 반환합니다."""
        logger.info(f"검색 요청: '{query}'")
        
        # 먼저 쿼리에서 위치 정보 확인
        params = self.parse_query(query)
        
        # 위치 정보(구, 동, 역) 중 하나라도 있는지 확인
        has_location = bool(params.get("gu") or params.get("dong") or params.get("station_name"))
        
        if not has_location:
            logger.info("위치 정보 없음 - 재질문 필요")
            return {
                "results": [],
                "message": "어느 지역의 매물을 찾으시나요? 예를 들어 '서초구', '방배동', '강남역 근처' 등으로 말씀해 주세요.",
                "requires_location": True
            }
        
        return self.hybrid_search(query, top_k)

    def format_response(self, results: Union[Dict[str, Any], List[Dict[str, Any]]], user_query: str) -> str:
        """검색 결과를 지정된 형식의 문자열로 변환합니다."""
        
        # 입력이 딕셔너리인 경우, 실제 결과 리스트를 추출합니다.
        if isinstance(results, dict):
            property_list = results.get("results", [])
        else:
            property_list = results

        if not property_list:
            return "조건에 맞는 매물이 없습니다."

        formatted_list = []
        for item in property_list:
            rank = item.get("rank", "")
            apt_name = item.get("aptNm", "이름 정보 없음")
            formatted_list.append(f"{rank}. {apt_name}")
        
        response_str = "\n".join(formatted_list)
        response_str += f"\n\n총 {len(property_list)}개의 매물을 찾았습니다."
        
        return response_str

    def get_station_info_from_data(self, meta: Dict[str, Any]) -> tuple:
        """데이터에서 역 정보 추출 (저장된 정보 우선 사용)"""
        try:
            # 저장된 역 정보 우선 사용
            stored_station = meta.get("nearest_station")
            stored_distance = meta.get("distance_to_station")
            
            if stored_station and stored_distance is not None:
                try:
                    distance_num = float(stored_distance)
                    if distance_num <= 2000:  # 2km 이내만 유효
                        return stored_station, f"{stored_station}({distance_num:.0f}m)"
                except (ValueError, TypeError):
                    pass
            
            return "정보없음", "정보없음"
            
        except Exception as e:
            logger.warning(f"역 정보 추출 실패: {e}")
            return "정보없음", "정보없음"

    def get_embedding(self, text: str) -> np.ndarray:
        """텍스트 임베딩 생성 (OpenAI 1.x 호환)"""
        retries, backoff = 3, 1
        for i in range(retries):
            try:
                r = openai_client.embeddings.create(model="text-embedding-3-small", input=[text])
                return np.array(r.data[0].embedding, dtype=np.float64)
            except Exception as e:
                if i < retries - 1:
                    logger.warning("임베딩 시도 %d 실패: %s, 재시도 %ds", i+1, e, backoff)
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    logger.error("임베딩 3회 실패: %s", e)
        return np.zeros(1536, dtype=np.float64)

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """간단한 문자열 유사도 계산 (한글 특화)"""
        if not str1 or not str2:
            return 0.0
        
        # 정확히 일치하는 경우
        if str1 == str2:
            return 1.0
        
        # 길이 차이가 큰 경우 낮은 점수
        len_diff = abs(len(str1) - len(str2))
        if len_diff > 2:
            return 0.0
        
        # 간단한 레벤슈타인 거리 계산
        def simple_levenshtein_ratio(s1, s2):
            if len(s1) == 0 or len(s2) == 0:
                return 0.0
            
            # 간단한 매트릭스 기반 계산
            rows = len(s1) + 1
            cols = len(s2) + 1
            dist = [[0 for _ in range(cols)] for _ in range(rows)]
            
            for i in range(1, rows):
                dist[i][0] = i
            for i in range(1, cols):
                dist[0][i] = i
            
            for col in range(1, cols):
                for row in range(1, rows):
                    if s1[row-1] == s2[col-1]:
                        cost = 0
                    else:
                        cost = 1
                    dist[row][col] = min(dist[row-1][col] + 1,      # deletion
                                       dist[row][col-1] + 1,        # insertion
                                       dist[row-1][col-1] + cost)   # substitution
            
            return 1 - (dist[row][col] / max(len(s1), len(s2)))
        
        # 기본 유사도 계산
        base_similarity = simple_levenshtein_ratio(str1, str2)
        
        # 한글 오타 보정 (간단한 패턴만)
        typo_bonus = 0.0
        if "서초" in str1 and any(x in str2 for x in ["서천", "서촌", "서쵸"]):
            typo_bonus = 0.3
        elif "서초" in str2 and any(x in str1 for x in ["서천", "서촌", "서쵸"]):
            typo_bonus = 0.3
        
        return min(1.0, base_similarity + typo_bonus)

    # 2차 파싱: 검색 작업이 결정된 후, 실제 검색에 필요한 상세 조건(지역, 가격 등)을 AI를 통해 추출합니다.
    def parse_query(self, q: str) -> Dict[str, Any]:
        """AI 기반 사용자 쿼리 파싱 (OpenAI Tool Calling 사용)"""
        logger.info(f"AI 쿼리 파싱 시작 (Tool Calling): '{q}'")
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": q}
                ],
                tools=[{"type": "function", "function": {"name": "search_parameters", "description": "부동산 검색 조건을 추출합니다.", "parameters": SearchParameters.model_json_schema()}}],
                tool_choice={"type": "function", "function": {"name": "search_parameters"}},
                temperature=0,
            )
            
            tool_call = response.choices[0].message.tool_calls[0]
            arguments = json.loads(tool_call.function.arguments)
            
            logger.info(f"AI 파싱 응답 (Tool Calling): {arguments}")

            # Pydantic 모델을 사용하여 검증 및 데이터 변환
            params = SearchParameters(**arguments)

            # 실제 데이터셋 필드명에 맞게 매핑
            result = {
                "gu": params.gu,
                "dong": params.dong,
                "dep_max": params.max_deposit,
                "mon_max": params.max_monthly,
                "require_rent": params.rent_type,
                "require_subway": params.is_subway_search,
                "max_dist": params.max_distance,
                "station_name": params.station_name
            }
            return result
        except Exception as e:
            logger.warning(f"AI 쿼리 파싱 실패, 백업 파싱 사용: {e}")
            return self._parse_query_fallback(q)

    def _parse_query_fallback(self, q: str) -> Dict[str, Any]:
        """
        AI 쿼리 파싱 실패 시 사용되는 규칙 기반 백업 파서.
        정규식을 사용하여 최소한의 검색 조건을 추출합니다.
        """
        logger.info(f"백업 파싱 사용: '{q}'")
        parsed = {
            "gu": None, "dong": None, "dep_max": None, "mon_max": None,
            "require_rent": None, "require_subway": False,
            "max_dist": 1000, "station_name": None
        }

        # 전세/월세 추출
        if "전세" in q:
            parsed["require_rent"] = "전세"
        elif "월세" in q:
            parsed["require_rent"] = "월세"

        # 보증금/월세 금액 추출 (단위: 만원)
        deposit_match = re.search(r"보증금\s*([\d,]+)\s*(억|천만|만)?", q)
        if deposit_match:
            amount = int(deposit_match.group(1).replace(",", ""))
            unit = deposit_match.group(2)
            if unit == "억":
                parsed["dep_max"] = amount * 10000
            elif unit == "천만":
                parsed["dep_max"] = amount * 1000
            else:
                parsed["dep_max"] = amount

        monthly_match = re.search(r"월세\s*([\d,]+)\s*(만)?", q)
        if monthly_match:
            parsed["mon_max"] = int(monthly_match.group(1).replace(",", ""))

        # 지역 및 역 이름 추출
        dong_match = re.search(r"(\w+[동|가|로])", q)
        if dong_match:
            parsed["dong"] = dong_match.group(1)

        gu_match = re.search(r"(\w+구)", q)
        if gu_match:
            parsed["gu"] = gu_match.group(1)
            
        station_match = re.search(r"(\w+역)", q)
        if station_match:
            station_name = station_match.group(1).replace("역", "")
            parsed["station_name"] = station_name
            parsed["require_subway"] = True

        logger.info(f"백업 파싱 결과: {parsed}")
        return parsed

    def _correct_typo_with_ai(self, input_text: str, candidates: List[str], text_type: str) -> str:
        """고도화된 AI 기반 오타 교정 프롬프트 사용"""
        if len(candidates) > 20:
            candidates = candidates[:20]
        candidates_text = ", ".join(candidates)
        user_prompt = f"""입력한 {text_type}: \"{input_text}\"
후보 목록: {candidates_text}
가장 유사한 정확한 {text_type} 이름을 선택해줘."""
        response = openai_client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": self.intelligent_correction_prompt},
                {"role": "user", "content": user_prompt}
            ],  
            temperature=0,
            max_tokens=50
        )
        ai_result = response.choices[0].message.content.strip()
        if ai_result and ai_result != "없음" and ai_result in candidates:
            return ai_result
        return None


    def hybrid_search(self, query: str, top_k: int = 30) -> Dict[str, Any]:
        """하이브리드 검색을 수행하고 결과를 사전 형태로 반환합니다."""
        logger.info(f"하이브리드 검색 시작: '{query}'")

        # 1. AI 기반 쿼리 파싱
        params = self.parse_query(query)
        
        # 2. 텍스트 검색 파이프라인 구성
        pipeline = []
        text_filter = {"$and": []}

        # 지역 필터
        if params.get("gu"):
            text_filter["$and"].append({"metadata.gu": params["gu"]})
        if params.get("dong"):
            text_filter["$and"].append({"metadata.dong": params["dong"]})

        # 임대 유형 필터
        if params.get("require_rent"):
            text_filter["$and"].append({"metadata.rent_type": params["require_rent"]})

        # 가격 필터
        if params.get("dep_max") is not None:
            text_filter["$and"].append({"metadata.deposit": {"$lte": params["dep_max"]}})
        if params.get("mon_max") is not None:
            text_filter["$and"].append({"metadata.monthlyRent": {"$lte": params["mon_max"]}})
            
        # 역세권 필터링: 역명과 거리 둘 다 적용
        if params.get("require_subway") and params.get("station_name"):
            text_filter["$and"].append({"metadata.nearest_station": params["station_name"]})
            text_filter["$and"].append({
                "metadata.distance_to_station": {"$lte": params["max_dist"]}
            })

        if text_filter["$and"]:
            pipeline.append({"$match": text_filter})

        # 3. 텍스트 검색 실행
        try:
            logger.info(f"텍스트 검색 실행: {json.dumps(pipeline, ensure_ascii=False)}")
            text_results = list(collection.aggregate(pipeline))
            logger.info(f"텍스트 검색 결과: {len(text_results)}개")
        except Exception as e:
            logger.error(f"텍스트 검색 실패: {e}")
            text_results = []

        # 4. 벡터 검색 실행
        query_embedding = self.get_embedding(query).tolist()
        vector_search_stage = {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": 150,
                "limit": VECTOR_LIMIT
            }
        }

        # 벡터 검색에 메타데이터 필터 적용
        if text_filter["$and"]:
            vector_search_stage["$vectorSearch"]["filter"] = text_filter

        vector_pipeline = [vector_search_stage, {"$limit": VECTOR_LIMIT}]
        try:
            logger.info("벡터 검색 실행")
            vector_results = list(collection.aggregate(vector_pipeline))
            logger.info(f"벡터 검색 결과: {len(vector_results)}개")
        except Exception as e:
            logger.error(f"벡터 검색 실패: {e}")
            vector_results = []

        # 5. RRF를 사용한 결과 병합
        ranked_results = defaultdict(float)
        for i, doc in enumerate(text_results):
            rank = i + 1
            ranked_results[doc['_id']] += TEXT_WEIGHT * (1 / (RANK_CONSTANT + rank))
        
        for i, doc in enumerate(vector_results):
            rank = i + 1
            ranked_results[doc['_id']] += VECTOR_WEIGHT * (1 / (RANK_CONSTANT + rank))

        if not ranked_results:
            logger.info("결합된 검색 결과 없음")
            return {"results": [], "message": "조건에 맞는 매물을 찾지 못했습니다."}

        # 6. 최종 결과 정렬 및 상위 K개 선택
        sorted_ids = sorted(ranked_results.keys(), key=lambda id: ranked_results[id], reverse=True)
        top_k_ids = sorted_ids[:top_k]

        final_results = list(collection.find({"_id": {"$in": top_k_ids}}))
        
        # 원래 순서대로 재정렬
        final_results.sort(key=lambda doc: top_k_ids.index(doc['_id']))

        # 7. 최종 결과 생성
        final_results_with_meta = []
        for doc in final_results:
            meta = doc.get("metadata", {}).copy()
            meta["_id"] = str(doc.get("_id"))  # _id를 문자열로 변환하여 추가
            meta["station_distance"] = meta.get("distance_to_station")
            final_results_with_meta.append(meta)

        # 역세권 필터링 (필요 시)
        if params.get("require_subway") and params.get("station_name"):
            final_results_with_meta = [
                meta for meta in final_results_with_meta
                if meta.get("nearest_station") == params["station_name"]
                and meta.get("distance_to_station", float('inf')) <= params["max_dist"]
            ]

        logger.info(f"최종 검색 결과: {len(final_results_with_meta)}개")
        logger.info("샘플 metadata_results: %s", final_results_with_meta[:3])

        if not final_results_with_meta:
            return {"results": [], "message": "조건에 맞는 매물을 찾지 못했습니다."}

        return {
            "results": [
                {
                    "rank": i + 1,
                    **meta,
                }
                for i, meta in enumerate(final_results_with_meta)
            ],
            "message": f"총 {len(final_results_with_meta)}개의 매물을 찾았습니다."
        }
    
    def _get_available_gus(self) -> list:
        """MongoDB에서 사용 가능한 구 목록을 불러오거나, 기본값 반환"""
        try:
            gus = collection.distinct("metadata.gu")
            return [g for g in gus if g]
        except Exception as e:
            logger.warning(f"구 목록 로드 실패: {e}")
            return ["서초구", "강남구", "송파구", "강동구"]
        