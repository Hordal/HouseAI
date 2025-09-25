import logging
import os
import json
from typing import List, Dict, Optional, Union, Tuple, Any
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from bson import ObjectId
from openai import OpenAI
from dotenv import load_dotenv
import numpy as np
from .utils import get_mongodb_collection

# utils.py의 add_rent_type_info 함수를 가져옵니다.
# 실제 환경에서는 from services.agents.utils import add_rent_type_info 와 같이 사용하세요.
def add_rent_type_info(docs: List[Dict]) -> List[Dict]:
    """
    문서 목록에 'rent_type' 필드가 없으면 기본값을 추가하는 임시 함수입니다.
    """
    for doc in docs:
        if 'rent_type' not in doc:
            # 기본 로직: deposit만 있으면 전세, monthlyRent가 있으면 월세로 간주
            if doc.get('deposit') and not doc.get('monthlyRent'):
                doc['rent_type'] = '전세'
            elif doc.get('deposit') and doc.get('monthlyRent'):
                doc['rent_type'] = '월세'
            else:
                doc['rent_type'] = '정보 없음'
    return docs


# 환경 변수 로드
load_dotenv()

# OpenAI 클라이언트 생성 (1.x 버전)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")
openai_client = OpenAI(api_key=OPENAI_API_KEY)



# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimilaritySearchAgent:
    """
    AI(LLM) 기반 유사도 검색 에이전트.
    임베딩 유사도와 필터 조건(보증금, 전세, 월세 등)을 결합한 하이브리드 검색을 지원합니다.
    """

    def __init__(
        self,
        property_collection: Optional[Collection] = None,
        openai_client: OpenAI = openai_client,
        vector_index_name: str = "vector_index",
        embedding_model: str = "text-embedding-3-small",
        candidate_factor: int = 10,
        limit_factor: int = 5,
    ):
        """
        SimilaritySearchAgent 클래스를 초기화합니다.

        Args:
            property_collection (Optional[Collection]): MongoDB 매물 컬렉션 객체.
            openai_client (OpenAI): OpenAI API 클라이언트.
            vector_index_name (str): MongoDB Atlas의 벡터 인덱스 이름.
            embedding_model (str): OpenAI 임베딩 모델 이름.
            candidate_factor (int): 벡터 검색 시 후보군 수 배율.
            limit_factor (int): 벡터 검색 시 초기 제한 수 배율.
        """
        if property_collection is None:
            try:
                property_collection = get_mongodb_collection(collection_env_var="APT_COLL")
                logger.info(f"MongoDB 컬렉션 로드 성공: {property_collection.full_name}")
            except Exception as e:
                raise RuntimeError(f"MongoDB 연결 실패: {e}")

        if not isinstance(property_collection, Collection):
            raise TypeError("property_collection은 PyMongo Collection 이어야 합니다.")
        if not hasattr(openai_client, "embeddings") or not hasattr(openai_client, "chat"):
            raise TypeError("openai_client는 embeddings 와 chat 속성을 가져야 합니다.")

        self.collection = property_collection
        self.openai_client = openai_client
        self.vector_index_name = vector_index_name
        self.embedding_model = embedding_model
        self.candidate_factor = candidate_factor
        self.limit_factor = limit_factor

        logger.info(
            f"Initialized SimilaritySearchAgent with index='{self.vector_index_name}', "
            f"model='{self.embedding_model}', collection='{self.collection.full_name}'"
        )

    def _understand_query_with_llm(self, query: str, conversation_history: Optional[List[Dict]] = None) -> Dict:
        """
        LLM(Function Calling)을 사용하여 사용자의 자연어 쿼리를 분석하고,
        검색에 필요한 핵심 검색어, 필터, 참조 인덱스 등을 구조화된 데이터로 추출합니다.

        Args:
            query (str): 사용자의 자연어 질문.
            conversation_history (Optional[List[Dict]]): 이전 대화 기록.

        Returns:
            Dict: LLM이 분석한 검색 파라미터 딕셔너리.
        """
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_properties",
                    "description": "사용자 쿼리를 기반으로 부동산 매물을 검색합니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query_text": {
                                "type": "string",
                                "description": "의미 기반 벡터 검색에 사용할 핵심 검색어입니다. (예: '조용한 주택가 아파트')",
                            },
                            "filters": {
                                "type": "object",
                                "description": "검색 결과를 필터링할 조건입니다.",
                                "properties": {
                                    "deposit": {"type": "object", "properties": {"$lte": {"type": "integer"}, "$gte": {"type": "integer"}}},
                                    "monthlyRent": {"type": "object", "properties": {"$lte": {"type": "integer"}, "$gte": {"type": "integer"}}},
                                    "area_pyeong": {"type": "object", "properties": {"$lte": {"type": "integer"}, "$gte": {"type": "integer"}}},
                                }
                            },
                            "reference_index": {
                                "type": "integer",
                                "description": "사용자가 이전에 본 매물 목록 중 특정 항목을 참조하는 경우, 해당 항목의 인덱스(1부터 시작)입니다."
                            }
                        },
                        "required": ["query_text"]
                    },
                },
            }
        ]

        messages = [
            {"role": "system", "content": "당신은 부동산 검색 쿼리 분석 전문가입니다. 사용자의 자연어 쿼리를 분석하여 `search_properties` 함수를 호출하기 위한 인자를 추출합니다. 모든 금액 단위는 '만원'으로 통일합니다. 예를 들어 '5억'은 50000으로 변환합니다. 사용자가 '1번 매물'이라고 하면 reference_index는 1입니다."}
        ]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": query})

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4.1",
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            tool_calls = response.choices[0].message.tool_calls
            if tool_calls:
                arguments = json.loads(tool_calls[0].function.arguments)
                logger.info(f"LLM이 추출한 검색 파라미터: {arguments}")
                return arguments
        except Exception as e:
            logger.error(f"LLM 쿼리 이해 실패: {e}", exc_info=True)
        
        return {"query_text": query, "filters": {}}

    def _identify_reference_property(self, reference_index: int, conversation_history: List[Dict]) -> Optional[Dict]:
        """
        대화 기록을 역순으로 탐색하여, 사용자가 'n번 매물'이라고 지칭한 특정 매물 정보를 찾아 반환합니다.

        Args:
            reference_index (int): 사용자가 언급한 매물의 순번 (1부터 시작).
            conversation_history (List[Dict]): 전체 대화 기록.

        Returns:
            Optional[Dict]: 찾은 매물 정보 딕셔너리. 못 찾으면 None.
        """
        if reference_index is None or not conversation_history:
            return None

        for msg in reversed(conversation_history):
            content = msg.get("content")
            if msg.get("role") == "assistant" and isinstance(content, str):
                try:
                    data = json.loads(content)
                    properties = data.get("results", []) 
                    actual_index = reference_index - 1
                    if isinstance(properties, list) and 0 <= actual_index < len(properties):
                        logger.info(f"참조 매물 발견 (인덱스 {reference_index}): {properties[actual_index].get('aptNm')}")
                        return properties[actual_index]
                except (json.JSONDecodeError, TypeError):
                    continue
        
        logger.warning(f"대화 기록에서 참조 매물(인덱스 {reference_index})을 찾지 못했습니다.")
        return None

    def search_similar_properties(
        self,
        query: Union[str, Dict],
        top_k: int = 10,
        min_score: float = 0.75,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        주어진 쿼리(자연어 또는 매물 객체)를 기반으로 유사한 매물을 검색하는 메인 로직을 수행합니다.

        Args:
            query (Union[str, Dict]): 사용자 쿼리 (텍스트 또는 매물 딕셔너리).
            top_k (int): 반환할 최대 결과 수.
            min_score (float): 최소 유사도 점수.
            conversation_history (Optional[List[Dict]]): 대화 기록.

        Returns:
            Dict[str, Any]: 검색 결과와 메시지를 담은 딕셔너리.
        """
        
        parsed_filters = {}
        base_id = None
        search_query_text_for_msg = ""

        if isinstance(query, str):
            llm_params = self._understand_query_with_llm(query, conversation_history)
            search_query_text = llm_params.get("query_text", query)
            search_query_text_for_msg = search_query_text
            parsed_filters = llm_params.get("filters", {})
            reference_index = llm_params.get("reference_index")

            if reference_index is not None:
                ref_property = self._identify_reference_property(reference_index, conversation_history)
                if ref_property:
                    query_vector, base_id = self._get_query_vector_and_id(ref_property)
                    search_query_text_for_msg = f"'{ref_property.get('aptNm', '선택 매물')}'와 비슷한"
                else:
                    query_vector, _ = self._get_query_vector_and_id(search_query_text)
            else:
                query_vector, _ = self._get_query_vector_and_id(search_query_text)

        elif isinstance(query, dict):
            search_query_text_for_msg = f"'{query.get('aptNm', '선택 매물')}'와 비슷한"
            query_vector, base_id = self._get_query_vector_and_id(query)
        
        else:
            return {"results": [], "message": "잘못된 타입의 쿼리입니다."}

        if query_vector is None:
            message = "쿼리 벡터 생성 실패: 유효한 텍스트 또는 문서 입력이 필요합니다."
            logger.error(message)
            return {"results": [], "message": message}
        
        logger.info(f"유사도 검색 실행. 최소 점수(min_score): {min_score}")
        pipeline = self._build_pipeline(query_vector, base_id, parsed_filters, top_k, min_score)
        logger.info(f"검색 파이프라인: {json.dumps(pipeline, indent=2, default=str)}")

        try:
            docs = list(self.collection.aggregate(pipeline))
            logger.info(f"검색 결과 건수: {len(docs)}")
        except PyMongoError as e:
            err = str(e)
            logger.error(f"MongoDB 집계 오류: {err}", exc_info=True)
            return {"results": [], "message": f"데이터베이스 검색 중 오류가 발생했습니다: {err}"}

        enhanced_docs = add_rent_type_info(docs)

        results = []
        for idx, doc in enumerate(enhanced_docs, start=1):
            doc["rank"] = idx
            doc["score"] = doc.get("similarity_score", 0.0)  # score 필드에 유사도 점수 추가
            results.append(doc)
        
        message = f"{search_query_text_for_msg} (으)로 총 {len(results)}개의 매물을 찾았습니다." if search_query_text_for_msg else f"총 {len(results)}개의 매물을 찾았습니다."
        return {"results": results, "message": message}

    def format_response(self, results: Dict[str, Any]) -> str:
        """
        검색 결과를 사용자가 보기 좋은 텍스트 형식으로 변환합니다.

        Args:
            results (Dict[str, Any]): search_similar_properties의 반환 값.

        Returns:
            str: 포맷팅된 결과 문자열.
        """
        items = results.get("results", [])
        if not items:
            return results.get("message", "조건에 맞는 매물이 없습니다.")
        
        lines = [
            f"{item['rank']}. {item.get('aptNm', '이름 정보 없음')}"
            for item in items
        ]
        response_str = "\n".join(lines)
        
        full_response = f"{results.get('message', '')}\n\n{response_str}"
        return full_response.strip()

    def respond(    
        self,
        query: Union[str, Dict],
        conversation_history: Optional[List[Dict]] = None,
        top_k: int = 10,
        min_score: float = 0.75,
        model: str = "gpt-4.1"
    ) -> Dict[str, str]:
        """
        전체 프로세스를 실행하여 최종 사용자 응답과 대화 기록용 데이터를 함께 반환합니다.

        Args:
            query (Union[str, Dict]): 사용자 쿼리.
            conversation_history (Optional[List[Dict]]): 대화 기록.
            top_k (int): 최대 결과 수.
            min_score (float): 최소 유사도 점수.
            model (str): 응답 생성에 사용할 LLM 모델.

        Returns:
            Dict[str, str]: 
                'display': 사용자에게 보여줄 친절한 설명.
                'history_content': 다음 턴을 위해 대화 기록에 저장할 JSON 데이터.
        """
        search_data = self.search_similar_properties(query, top_k, min_score, conversation_history)
        
        history_content = json.dumps(search_data, ensure_ascii=False, default=str)
        
        response_text = self.format_response(search_data)
        display_message = response_text

        try:
            if search_data.get("results"):
                summary = response_text
                llm_resp = self.openai_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "당신은 부동산 매물 추천 에이전트입니다. 검색 결과를 바탕으로 사용자에게 친절하게 설명해주세요."},
                        {"role": "user", "content": f"다음 매물 목록을 사용자에게 이해하기 쉽게 설명해 주세요:\n{summary}"}
                    ],
                    temperature=0.7
                )
                display_message = llm_resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"응답 생성 중 LLM 호출 실패: {e}")

        return {
            "display": display_message,
            "history_content": history_content
        }

    def _get_query_vector_and_id(
        self, query: Union[str, Dict]
    ) -> Tuple[Optional[List[float]], Optional[ObjectId]]:
        """
        쿼리(텍스트 또는 매물 객체)로부터 벡터 검색에 사용할 임베딩 벡터와
        참조 매물의 ID를 생성합니다.

        - 텍스트 쿼리: 텍스트를 직접 임베딩합니다.
        - 매물 객체 쿼리: 객체에 'embedding'이 있으면 바로 사용하고, 없으면
                         가격을 제외한 고유 특성으로 텍스트를 만들어 임베딩합니다.

        Args:
            query (Union[str, Dict]): 사용자 쿼리.

        Returns:
            Tuple[Optional[List[float]], Optional[ObjectId]]: 생성된 임베딩 벡터와 참조 매물의 ID.
        """
        if isinstance(query, str):
            emb = self._generate_embedding(query)
            return emb, None
        
        if isinstance(query, dict):
            base_id_str = str(query.get("_id"))
            oid = ObjectId(base_id_str) if base_id_str else None

            if 'embedding' in query and query['embedding']:
                logger.info("참조 매물에서 기존 임베딩을 사용합니다.")
                return query['embedding'], oid

            logger.warning(f"참조 매물에 임베딩이 없어 DB에서 재조회합니다. (_id={base_id_str})")
            if not oid:
                return None, None
            
            try:
                full_doc = self.collection.find_one({"_id": oid})
            except Exception as e:
                logger.error(f"문서 조회 실패 (_id={base_id_str}): {e}")
                return None, None
            
            if not full_doc:
                logger.error(f"DB에서 문서를 찾을 수 없습니다 (_id={base_id_str})")
                return None, None

            # DB에서 조회한 문서가 metadata를 포함할 경우를 대비
            metadata = full_doc.get("metadata", full_doc)

            apt_name = metadata.get('aptNm', '')
            dong = metadata.get('dong', '')
            area = metadata.get('area_pyeong', 0)
            
            rent_type = metadata.get('rent_type', '')
            if not rent_type:
                rent_type = '월세' if metadata.get('monthlyRent') else '전세'

            text_parts = [dong, apt_name, f"{area}평", rent_type]
            text = " ".join(filter(None, text_parts)).strip()
            
            logger.info(f"참조 매물 기반 임베딩 생성용 텍스트: '{text}'")
            
            emb = self._generate_embedding(text)
            return emb, oid
        
        return None, None

    def _build_pipeline(
        self,
        query_vector: List[float],
        base_id: Optional[ObjectId],
        filters: Optional[Dict],
        top_k: int,
        min_score: float,
    ) -> List[Dict]:
        """
        MongoDB Aggregation Pipeline을 동적으로 생성합니다.
        벡터 검색, 필드 프로젝션, 필터링, 결과 제한 단계를 포함합니다.

        Args:
            query_vector (List[float]): 검색에 사용할 임베딩 벡터.
            base_id (Optional[ObjectId]): 참조 매물의 ID (결과에서 제외하기 위함).
            filters (Optional[Dict]): 적용할 추가 필터 조건.
            top_k (int): 최종 결과 수.
            min_score (float): 최소 유사도 점수.

        Returns:
            List[Dict]: 생성된 MongoDB Aggregation Pipeline.
        """
        num_candidates = top_k * self.candidate_factor
        limit_count = top_k * self.limit_factor

        match_conditions = {"similarity_score": {"$gte": min_score}}
        if base_id:
            match_conditions["_id"] = {"$ne": base_id}
        
        if filters:
            for k, v in filters.items():
                # [핵심 수정] 필터링 시 'metadata.' 접두사를 다시 추가합니다.
                match_conditions[f"metadata.{k}"] = v

        return [
            {
                "$vectorSearch": {
                    "index": self.vector_index_name,
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": num_candidates,
                    "limit": limit_count,
                }
            },
            {
                # [핵심 수정] 프로젝션 시 'metadata.' 접두사를 다시 추가합니다.
                "$project": {
                    "similarity_score": {"$meta": "vectorSearchScore"},
                    "_id": 1,
                    "gu": "$metadata.gu",
                    "dong": "$metadata.dong",
                    "jibun": "$metadata.jibun",
                    "aptNm": "$metadata.aptNm",
                    "floor": "$metadata.floor",
                    "area_pyeong": "$metadata.area_pyeong",
                    "deposit": "$metadata.deposit",
                    "monthlyRent": "$metadata.monthlyRent",
                    "rent_type": "$metadata.rent_type",
                    "isAvailable": "$metadata.isAvailable",
                    "lat": "$metadata.lat",
                    "lng": "$metadata.lng",
                    "nearest_station": "$metadata.nearest_station",
                    "distance_to_station": "$metadata.distance_to_station",
                    "embedding": "$embedding"
                },
            },
            {"$match": match_conditions},
            {"$limit": top_k},
        ]

    def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        주어진 텍스트를 OpenAI 임베딩 모델을 사용하여 벡터로 변환합니다.

        Args:
            text (str): 벡터로 변환할 텍스트.

        Returns:
            Optional[List[float]]: 생성된 임베딩 벡터. 실패 시 None.
        """
        text = (text or "").strip()
        if not text:
            return np.zeros(1536, dtype=float).tolist()
        try:
            resp = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=[text]
            )
            return resp.data[0].embedding
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {e}")
            return None
