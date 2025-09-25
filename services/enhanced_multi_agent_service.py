"""
Enhanced Multi-Agent System for HouseAI
진정한 협력형 다중 에이전트 시스템 (LangChain Tools 기반)

이 시스템은 여러 에이전트가 동시에 협력하여 복잡한 요청을 처리합니다.
- LangChain Tools와 Agent 기반 아키텍처
- 에이전트 간 메시지 전달 및 협력
- 병렬 처리 및 파이프라인 실행
- 상태 공유 및 협업
- PropertyItem 스키마 기반 데이터 통일
- Claude와 OpenAI 모델 지원
"""

import os
import re
import json
import tempfile
import datetime
import time
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import traceback

# LangChain 및 관련 라이브러리
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain.agents import tool, AgentExecutor, create_react_agent
from langchain.memory import ConversationBufferMemory

# Claude 지원을 위한 import 추가
try:
    from langchain_anthropic import ChatAnthropic
    CLAUDE_AVAILABLE = True
    print("✅ Claude support enabled (langchain_anthropic available)")
except ImportError as e:
    CLAUDE_AVAILABLE = False
    print(f"❌ Claude support disabled: {e}")
    print("💡 To enable Claude: pip install anthropic langchain-anthropic")

# Agent imports
from services.agents import (
    SearchAgent, 
    ChatAgent,
    WishlistLAM,
    add_rent_type_info,
    multi_agent_logger
)

from services.agents.analysis_agent import AnalysisAgent
from services.agents.recommendation_agent import RecommendationAgent
from services.agents.comparison_agent import ComparisonAgent
from services.agents.sim_search_agent import SimilaritySearchAgent

from services.list_services import get_wishlist
from db.database import get_db

from services.agents.utils import extract_location_from_query, resolve_references
from pydantic import BaseModel

class TaskType(Enum):
    """작업 타입 정의"""
    SEARCH = "search"
    SIMILARITY_SEARCH = "similarity_search"
    ANALYSIS = "analysis"
    RECOMMENDATION = "recommendation"
    COMPARISON = "comparison"
    WISHLIST = "wishlist"
    CHAT = "chat"

class Priority(Enum):
    """작업 우선순위"""
    HIGH = 1
    MEDIUM = 2
    LOW = 3

@dataclass
class AgentTask:
    """에이전트 작업 정의"""
    task_id: str
    task_type: TaskType
    description: str
    data: Dict[str, Any] = field(default_factory=dict)
    priority: Priority = Priority.MEDIUM
    dependencies: List[str] = field(default_factory=list)  # 의존성 작업 ID
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class TaskParser:
    """사용자 요청을 여러 작업으로 분해하는 클래스 (LangChain 기반)"""
    
    def __init__(self):
        self.search_keywords = [
            "찾아줘", "검색", "추천", "매물", "전세", "월세", "보증금", 
            "역세권", "근처", "아파트", "원룸", "투룸"
        ]
        self.analysis_keywords = [
            "분석", "장점", "단점", "특이사항", "특징", "자세히", "정보", "설명", "알려줘",
            "생각해", "의견", "어때", "평가", "어떻게", "어떨까", "살펴봐", "확인해"
        ]
        self.recommendation_keywords = [
            "추천", "추천해줘", "추천해", "선택", "고르", "결정", "제일", "가장", "최고", "최저", 
            "어떤게", "어떤", "괜찮은", "괜찮", "적합", "맞는", "어울리는", "어울려", 
            "좋을까", "나을까", "최적", "베스트", "TOP", "좋은", "나쁜", "살기", "거주",
            "4인가족", "신혼부부", "1인가구", "가족", "구성", "생활", "주거"
        ]
        self.comparison_keywords = [
            "비교", "비교해줘", "비교해", "차이", "차이점", "다른점", "다름", "다르",
            "대비", "vs", "와", "과", "대조", "비교분석", "대비해", "비교해서"
        ]
        self.wishlist_keywords = [
            "찜", "저장", "좋아요", "찜목록", "찜한", "저장된"
        ]
        self.similar_search_keywords = [
            "비슷한", "유사한", "같은", "닮은", "비슷하게", "유사하게"
        ]
        # 유사 검색 패턴 추가
        self.similarity_search_patterns = [
            r'(\d+)번.*?(비슷한|유사한|같은|닮은)',
            r'(\d+)번.*?매물.*?(비슷한|유사한|같은|닮은)',
            r'(\d+)번.*?(와|과).*?(비슷한|유사한|같은)',
            r'([가-힣\w\d\s]+아파트).*?(비슷한|유사한|같은)',
            r'([가-힣\w\d\s]+타워).*?(비슷한|유사한|같은)',
            r'이런.*?(비슷한|유사한|같은).*?매물',
            r'이와.*?(비슷한|유사한|같은).*?매물',
            r'이것과.*?(비슷한|유사한|같은)',
            r'.*?(비슷한|유사한|같은).*?매물.*?찾아',
            r'.*?(비슷한|유사한|같은).*?조건.*?찾아'
        ]
        # 기존 결과에 대한 분석 요청 패턴
        self.existing_analysis_patterns = [
            r'(\d+)번.*?(생각해|의견|어때|평가|분석|좋은|나쁜|어떤)',
            r'(\d+)번.*?(매물).*?(생각해|의견|어때|평가|분석|좋은|나쁜|어떤)',
            r'(\d+)번.*?(추천|선택|고르|결정)'
        ]
        
        # 기존 결과에 대한 추천 요청 패턴
        self.existing_recommendation_patterns = [
            r'검색.*된.*매물.*중에.*추천',
            r'검색.*결과.*중에.*추천',
            r'검색.*매물.*중에.*추천',
            r'검색.*된.*중에.*추천',
            r'검색.*결과.*추천',
            r'검색.*매물.*추천',
            r'위.*매물.*중에.*추천',
            r'위.*결과.*중에.*추천',
            r'위.*중에.*추천',
            r'현재.*매물.*중에.*추천',
            r'현재.*결과.*중에.*추천',
            r'찾은.*매물.*중에.*추천',
            r'찾은.*결과.*중에.*추천',
            r'.*매물.*중에.*추천',
            r'.*결과.*중에.*추천',
            r'.*중에.*4인.*가족',
            r'.*중에.*신혼부부',
            r'.*중에.*1인.*가구',
            r'.*중에.*가족.*구성',
            r'.*중에.*살기.*좋은'
        ]
        
        # 복합 패턴 감지를 위한 연결어
        self.compound_connectors = ["그리고", "또한", "그 중", "그중", "중에서", "에서"]

        # LangChain 설정은 EnhancedMultiAgentOrchestrator에서 통일 관리
        self.llm = None  # 초기화 시 설정
        
        # LLM 기반 의도 분석을 위한 프롬프트 템플릿
        self.intent_analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", """
            당신은 부동산 매물 검색 서비스의 사용자 의도 분석 전문가입니다.
            사용자의 질문을 분석하여 어떤 에이전트가 처리해야 할지 판단해주세요.
            
            사용 가능한 에이전트 타입:
            1. SEARCH - 새로운 매물 검색 (예: "서초구 전세 매물 찾아줘")
            2. SIMILARITY_SEARCH - 특정 매물과 유사한 매물 검색 (예: "2번 매물과 비슷한 매물 찾아줘")
            3. ANALYSIS - 매물 분석 (예: "이 매물들의 장단점 분석해줘")
            4. RECOMMENDATION - 매물 추천 (예: "가장 좋은 매물 추천해줘")
            5. COMPARISON - 매물 비교 (예: "1번과 2번 매물 비교해줘")
            6. WISHLIST - 찜 목록 관리 (예: "찜 목록 보여줘")
            7. CHAT - 일반 대화 (예: "안녕하세요")
            
            위치 정보 부족 시 처리:
            - "집 좀 찾아줘", "매물 찾아줘", "월세 매물 찾아줘" 등에서 위치 정보(구, 동, 역)가 없으면 → CHAT (위치 재질문)
            - "방배동이야", "서초구야", "강남역 근처야" 등 위치만 제공된 경우 → 이전 대화의 조건과 결합하여 SEARCH 처리
            
            대화 맥락 고려 규칙:
            - 이전에 "월세 집 찾아줘"라고 했고, 다음에 "방배동이야"라고 하면 → "방배동 월세" 검색으로 처리
            - 이전에 "전세 매물 찾아줘"라고 했고, 다음에 "서초구"라고 하면 → "서초구 전세" 검색으로 처리
            
            복합 요청 처리 규칙:
            - "찾고 추천", "찾아서 추천" → SEARCH + RECOMMENDATION (순차 처리)
            - "추천 다음 비교", "추천한 다음 비교" → RECOMMENDATION + COMPARISON (순차 처리)
            - "비교하고 분석", "비교 후 분석" → COMPARISON + ANALYSIS (순차 처리)
            - "서초역 전세 매물을 찾고 괜찮은 매물을 추천한 다음 1번과 2번을 비교해주고 3번을 분석해줘" 
              → SEARCH + RECOMMENDATION + COMPARISON + ANALYSIS (순차 처리)
            
            특별 주의사항:
            - "검색된 매물 중에서", "찾은 매물 중에서", "위 매물 중에서", "결과 중에서" 등의 표현이 있고 "추천"이 포함된 경우 → RECOMMENDATION (requires_existing_data: true)
            - "4인 가족", "신혼부부", "1인 가구" 등 특정 가족 구성에 대한 추천 → RECOMMENDATION (requires_existing_data: true)
            - 새로운 검색이 아닌 기존 결과에 대한 추천임을 정확히 판단하세요
            
            컨텍스트 정보:
            - 기존 검색 결과 존재: {has_existing_results}
            - 사용자 ID: {user_id}
            
            응답 형식 (JSON):
            {{
                "primary_intent": "에이전트_타입",
                "secondary_intents": ["보조_에이전트_타입들"],
                "confidence": 0.95,
                "requires_existing_data": true/false,
                "reasoning": "판단 근거 설명",
                "is_complex_request": true/false,
                "needs_location_context": true/false
            }}
            """),
            ("human", "사용자 질문: {user_query}")
        ])
        
        # 복합 작업 분석을 위한 프롬프트
        self.complex_task_prompt = ChatPromptTemplate.from_messages([
            ("system", """
            사용자의 복합적인 요청을 분석하여 필요한 작업 순서를 결정해주세요.
            
            예시:
            - "서초역 전세 매물을 찾고 괜찮은 매물을 추천한 다음 1번과 2번을 비교해주고 3번을 분석해줘" 
              → SEARCH → RECOMMENDATION → COMPARISON → ANALYSIS
            - "강남구 전세 매물 찾아서 추천해줘" → SEARCH → RECOMMENDATION  
            - "매물 비교하고 가장 좋은 것 추천해줘" → COMPARISON → RECOMMENDATION
            - "찜 목록 분석해서 비슷한 매물 찾아줘" → WISHLIST → ANALYSIS → SIMILARITY_SEARCH
            - "2번 매물과 비슷한 매물 찾아서 분석해줘" → SIMILARITY_SEARCH → ANALYSIS
            
            중요한 작업 순서 규칙:
            1. 검색(SEARCH) → 추천(RECOMMENDATION) → 비교(COMPARISON) → 분석(ANALYSIS) 순서로 진행
            2. 특정 번호 매물 분석이나 비교는 반드시 검색 후에 실행
            3. 각 작업 간에는 적절한 의존성을 설정
            
            응답 형식 (JSON):
            {{
                "tasks": [
                    {{
                        "task_type": "SEARCH",
                        "description": "매물 검색",
                        "priority": "HIGH",
                        "dependencies": []
                    }},
                    {{
                        "task_type": "RECOMMENDATION", 
                        "description": "매물 추천",
                        "priority": "MEDIUM",
                        "dependencies": ["SEARCH"]
                    }},
                    {{
                        "task_type": "COMPARISON",
                        "description": "매물 비교",
                        "priority": "MEDIUM",
                        "dependencies": ["RECOMMENDATION"]
                    }},
                    {{
                        "task_type": "ANALYSIS",
                        "description": "매물 분석",
                        "priority": "MEDIUM",
                        "dependencies": ["COMPARISON"]
                    }}
                ]
            }}
            """),
            ("human", "사용자 요청: {user_query}")
        ])
        
    def parse_user_request(self, user_query: str, user_id: Optional[int] = None) -> List['AgentTask']:
        try:
            multi_agent_logger.info(f"TaskParser 분석 중: '{user_query}'")
            if self.llm:
                llm_tasks = self._analyze_intent_with_llm(user_query, user_id)
                if llm_tasks:
                    multi_agent_logger.info(f"✅ [LLM 분석] 성공 - {len(llm_tasks)}개 작업 생성")
                    return llm_tasks
                else:
                    multi_agent_logger.warning("LLM 기반 의도 분석 실패, 키워드 분석으로 폴백")
            return self._analyze_intent_with_keywords(user_query, user_id)
        except Exception as e:
            multi_agent_logger.error(f"작업 분석 오류: {e}")
            chat_task = AgentTask(
                task_id="chat_001",
                task_type=TaskType.CHAT,
                description="일반 대화 처리 (오류 대체)",
                data={"query": user_query},
                priority=Priority.LOW
            )
            return [chat_task]
    
    def _analyze_intent_with_llm(self, user_query: str, user_id: Optional[int] = None) -> Optional[List['AgentTask']]:
        try:
            # LLM이 설정되지 않은 경우 키워드 분석으로 폴백
            if not self.llm:
                multi_agent_logger.warning("LLM이 설정되지 않아 키워드 분석으로 폴백")
                return None
                
            # 기존 검색 결과 확인
            storage_path = os.path.join(tempfile.gettempdir(), "search_history.json")
            has_existing_results = os.path.exists(storage_path) and os.path.getsize(storage_path) > 0
            
            # LLM을 통한 의도 분석
            prompt = self.intent_analysis_prompt.format_messages(
                user_query=user_query,
                has_existing_results=has_existing_results,
                user_id=user_id
            )
            
            response = self.llm.invoke(prompt)
            intent_text = response.content
            
            # JSON 파싱 시도
            try:
                # 코드 블록 제거
                if "```json" in intent_text:
                    intent_text = intent_text.split("```json")[1].split("```")[0]
                elif "```" in intent_text:
                    intent_text = intent_text.split("```")[1].split("```")[0]
                
                intent_data = json.loads(intent_text.strip())
                multi_agent_logger.info(f"LLM 의도 분석 결과: {intent_data}")
                
                # 단순 작업인지 복합 작업인지 판단
                if intent_data.get("secondary_intents") or intent_data.get("is_complex_request", False):
                    return self._create_complex_tasks_from_llm(user_query, intent_data, user_id)
                else:
                    return self._create_simple_task_from_llm(user_query, intent_data, user_id)
                    
            except json.JSONDecodeError as e:
                multi_agent_logger.error(f"LLM 응답 JSON 파싱 실패: {e}, 응답: {intent_text}")
                return None
                
        except Exception as e:
            multi_agent_logger.error(f"LLM 의도 분석 오류: {e}")
            return None

    def _create_simple_task_from_llm(self, user_query: str, intent_data: Dict, user_id: Optional[int] = None) -> List['AgentTask']:
        primary_intent = intent_data.get("primary_intent")
        requires_existing_data = intent_data.get("requires_existing_data", False)
        needs_location_context = intent_data.get("needs_location_context", False)
        
        # 검색 기록 로드
        storage_path = os.path.join(tempfile.gettempdir(), "search_history.json")
        lines = []
        if os.path.exists(storage_path):
            with open(storage_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        search_history = []
        if lines:
            try:
                for line in lines:
                    entry = json.loads(line.strip())
                    search_history.append({
                        "query": entry.get("query"),
                        "location": extract_location_from_query(entry.get("query", "")),
                        "result": {"results": entry.get("results", []), "total_count": len(entry.get("results", []))}
                    })
            except Exception:
                pass
        
        # 현재 쿼리의 지역 정보 추출
        current_location = extract_location_from_query(user_query)
        multi_agent_logger.info(f"현재 쿼리 위치: {current_location}")
        
        # 대화 맥락을 고려한 위치 정보 보완 로직
        enhanced_query = user_query
        
        # "방배동이야", "서초구야" 등 위치만 제공된 경우 패턴 확인
        location_only_patterns = [
            r"^([가-힣]+구)야?$", r"^([가-힣]+동)야?$", r"^([가-힣]+역)\s*(근처)?야?$",
            r"^([가-힣]+구)\s*에서\s*찾아줘?$", r"^([가-힣]+동)\s*에서\s*찾아줘?$"
        ]
        is_location_only = any(re.match(pattern, user_query.strip()) for pattern in location_only_patterns)
        
        if is_location_only and search_history:
            multi_agent_logger.info(f"위치만 제공된 쿼리 감지: '{user_query}'")
            
            # 최근 검색 기록에서 조건을 찾음 (최대 5개 기록 확인)
            previous_conditions = []
            search_conditions = ["월세", "전세", "매매", "오피스텔", "아파트", "빌라", "원룸", "투룸", "쓰리룸"]
            
            # 최근 기록부터 역순으로 확인하여 조건 추출
            for history_item in reversed(search_history[-5:]):  # 최근 5개 기록만 확인
                history_query = history_item.get("query", "")
                multi_agent_logger.info(f"기록 확인: '{history_query}'")
                
                # 검색 조건 추출
                for condition in search_conditions:
                    if condition in history_query and condition not in previous_conditions:
                        previous_conditions.append(condition)
                        multi_agent_logger.info(f"조건 발견: {condition}")
                
                # 기본적인 "집", "매물" 키워드도 확인
                if ("집" in history_query or "매물" in history_query) and "매물" not in previous_conditions:
                    previous_conditions.append("매물")
                    multi_agent_logger.info(f"조건 발견: 매물")
                
                # 조건을 찾았으면 중단
                if previous_conditions:
                    break
            
            if previous_conditions:
                # 위치 정보 정리 ("야", "에서 찾아줘" 등 제거)
                clean_location = user_query.replace('야', '').replace('에서 찾아줘', '').replace('에서', '').strip()
                enhanced_query = f"{clean_location} {' '.join(previous_conditions)}"
                multi_agent_logger.info(f"대화 맥락 결합: '{user_query}' + 이전 조건{previous_conditions} → '{enhanced_query}'")
            else:
                multi_agent_logger.info("이전 조건을 찾지 못함, 일반 검색으로 처리")
        
        elif primary_intent == "SEARCH" and not current_location and search_history:
            # 위치 정보가 없는 일반 검색 요청의 경우
            latest_entry = search_history[-1]
            latest_query = latest_entry.get("query", "")
            
            # 이전 질문에서 조건을 추출해서 결합 (기존 로직 유지)
            previous_conditions = []
            if "월세" in latest_query:
                previous_conditions.append("월세")
            elif "전세" in latest_query:
                previous_conditions.append("전세")
            if "매물" in latest_query or "집" in latest_query:
                previous_conditions.append("매물")
            
            if previous_conditions:
                enhanced_query = f"{user_query} {' '.join(previous_conditions)}"
                multi_agent_logger.info(f"위치 정보 보완: '{user_query}' → '{enhanced_query}'")
        
        # 위치 정보가 여전히 없고 검색 요청인 경우 → CHAT으로 변환하여 재질문
        if primary_intent == "SEARCH":
            # 보완된 쿼리에서 다시 위치 확인
            enhanced_location = extract_location_from_query(enhanced_query)
            if not enhanced_location:
                multi_agent_logger.info("검색 요청이지만 위치 정보 없음 → 재질문으로 변환")
                chat_task = AgentTask(
                    task_id="location_request",
                    task_type=TaskType.CHAT,
                    description="위치 정보 재질문",
                    data={
                        "query": user_query,
                        "response": "어느 지역의 매물을 찾으시나요? 예를 들어 '서초구', '방배동', '강남역 근처' 등으로 말씀해 주세요."
                    },
                    priority=Priority.HIGH
                )
                return [chat_task]
        
        # 보완된 쿼리로 작업 생성
        final_query = enhanced_query if enhanced_query != user_query else user_query
        
        # 기존 데이터가 필요한 경우 처리
        if requires_existing_data:
            if primary_intent == "COMPARISON":
                norm_query = user_query
                m = re.match(r'([가-힣]+동 \d+번)\s+([가-힣]+동 \d+번)', norm_query)
                if m:
                    norm_query = f"{m.group(1)}, {m.group(2)}" + norm_query[m.end():]
                refs = resolve_references(norm_query, search_history)
                if not refs or len(refs) < 2:
                    chat_task = AgentTask(
                        task_id="chat_no_results",
                        task_type=TaskType.CHAT,
                        description="기존 결과 없음 - 일반 대화",
                        data={"query": user_query},
                        priority=Priority.LOW
                    )
                    return [chat_task]
                task_type_map = {
                    "SEARCH": TaskType.SEARCH,
                    "ANALYSIS": TaskType.ANALYSIS,
                    "RECOMMENDATION": TaskType.RECOMMENDATION,
                    "COMPARISON": TaskType.COMPARISON,
                    "WISHLIST": TaskType.WISHLIST,
                    "CHAT": TaskType.CHAT
                }
                task_type = task_type_map.get(primary_intent, TaskType.CHAT)
                task = AgentTask(
                    task_id=f"llm_{primary_intent.lower()}_001",
                    task_type=task_type,
                    description=f"LLM 분석 기반 {primary_intent} 작업",
                    data={
                        "query": user_query,
                        "source": "existing",
                        "llm_reasoning": intent_data.get("reasoning", ""),
                        "properties": refs
                    },
                    priority=Priority.HIGH
                )
                return [task]
            
            elif primary_intent == "RECOMMENDATION":
                # 추천 요청인 경우 해당 지역의 기존 검색 결과 확인
                region_results = None
                has_matching_region_results = False

                if current_location and search_history:
                    # 같은 지역의 검색 결과 찾기
                    for history_item in reversed(search_history):  # 최신 결과부터 확인
                        history_location = history_item.get("location")
                        if history_location == current_location:
                            results = history_item["result"].get("results", [])
                            if isinstance(results, list) and len(results) > 0:
                                region_results = results
                                has_matching_region_results = True
                                multi_agent_logger.info(f"기존 {current_location} 검색 결과 발견: {len(results)}개 매물")
                                break
                elif not current_location and search_history:
                    # 지역 정보가 없으면 최신 검색 결과 사용
                    latest_results = search_history[-1]["result"].get("results", [])
                    if isinstance(latest_results, list) and len(latest_results) > 0:
                        region_results = latest_results
                        has_matching_region_results = True
                        multi_agent_logger.info(f"지역 정보 없음, 최신 검색 결과({len(latest_results)}개)로 추천")

                if has_matching_region_results:
                    # 기존 지역 결과 또는 최신 결과로 추천
                    task = AgentTask(
                        task_id=f"llm_recommendation_existing_region",
                        task_type=TaskType.RECOMMENDATION,
                        description=f"{current_location if current_location else '최신'} 기존 검색 결과로 추천",
                        data={
                            "query": user_query,
                            "source": "existing",
                            "region": current_location,
                            "properties": region_results,
                            "llm_reasoning": intent_data.get("reasoning", "")
                        },
                        priority=Priority.HIGH
                    )
                    return [task]
                else:
                    # 해당 지역의 기존 결과가 없으면 새로 검색 후 추천
                    multi_agent_logger.info(f"{current_location} 지역의 기존 검색 결과 없음, 새로 검색")
                    search_task = AgentTask(
                        task_id="search_for_recommendation",
                        task_type=TaskType.SEARCH,
                        description=f"{current_location} 매물 검색",
                        data={"query": user_query, "region": current_location},
                        priority=Priority.HIGH
                    )
                    recommendation_task = AgentTask(
                        task_id="recommendation_after_search",
                        task_type=TaskType.RECOMMENDATION,
                        description=f"{current_location} 검색 결과로 추천",
                        data={
                            "query": user_query, 
                            "source": "search", 
                            "region": current_location,
                            "llm_reasoning": intent_data.get("reasoning", "")
                        },
                        dependencies=["search_for_recommendation"],
                        priority=Priority.MEDIUM
                    )
                    return [search_task, recommendation_task]
            
            else:
                # 기타 기존 데이터 필요한 작업들
                has_existing_results = False
                if search_history:
                    last_result = search_history[-1]
                    results = last_result["result"].get("results", []) if isinstance(last_result, dict) and "result" in last_result else []
                    if isinstance(results, list) and results:
                        has_existing_results = True
                
                if not has_existing_results:
                    chat_task = AgentTask(
                        task_id="chat_no_results",
                        task_type=TaskType.CHAT,
                        description="기존 결과 없음 - 일반 대화",
                        data={"query": user_query},
                        priority=Priority.LOW
                    )
                    return [chat_task]
        
        # 일반 작업 생성
        task_type_map = {
            "SEARCH": TaskType.SEARCH,
            "SIMILARITY_SEARCH": TaskType.SIMILARITY_SEARCH,
            "ANALYSIS": TaskType.ANALYSIS,
            "RECOMMENDATION": TaskType.RECOMMENDATION,
            "COMPARISON": TaskType.COMPARISON,
            "WISHLIST": TaskType.WISHLIST,
            "CHAT": TaskType.CHAT
        }
        task_type = task_type_map.get(primary_intent, TaskType.CHAT)
        task = AgentTask(
            task_id=f"llm_{primary_intent.lower()}_001",
            task_type=task_type,
            description=f"LLM 분석 기반 {primary_intent} 작업",
            data={
                "query": final_query,  # 보완된 쿼리 사용
                "original_query": user_query,  # 원본 쿼리도 보존
                "source": "existing" if requires_existing_data else "new",
                "llm_reasoning": intent_data.get("reasoning", "")
            },
            priority=Priority.HIGH
        )
        return [task]

    def _create_complex_tasks_from_llm(self, user_query: str, intent_data: Dict, user_id: Optional[int] = None) -> List['AgentTask']:
        try:
            complex_chain = self.complex_task_prompt | self.llm
            response = complex_chain.invoke({"user_query": user_query})
            
            # JSON 파싱 처리
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            complex_data = json.loads(content.strip())
            tasks = []
            
            task_type_map = {
                "SEARCH": TaskType.SEARCH,
                "SIMILARITY_SEARCH": TaskType.SIMILARITY_SEARCH,
                "ANALYSIS": TaskType.ANALYSIS,
                "RECOMMENDATION": TaskType.RECOMMENDATION,
                "COMPARISON": TaskType.COMPARISON,
                "WISHLIST": TaskType.WISHLIST,
                "CHAT": TaskType.CHAT
            }
            priority_map = {
                "HIGH": Priority.HIGH,
                "MEDIUM": Priority.MEDIUM,
                "LOW": Priority.LOW
            }

            # 1. 먼저 task_type별로 task_id 매핑 생성
            type_to_id = {}
            for i, task_data in enumerate(complex_data.get("tasks", [])):
                task_type_str = task_data.get("task_type")
                task_id = f"llm_complex_{i+1:03d}"
                type_to_id[task_type_str] = task_id

            # 2. AgentTask 생성 (dependencies를 실제 task_id로 변환)
            for i, task_data in enumerate(complex_data.get("tasks", [])):
                task_type = task_type_map.get(task_data.get("task_type"), TaskType.CHAT)
                priority = priority_map.get(task_data.get("priority"), Priority.MEDIUM)
                dep_types = task_data.get("dependencies", [])
                dep_ids = [type_to_id.get(dep) for dep in dep_types if dep in type_to_id]
                
                # 작업별 데이터 설정
                task_data_dict = {
                    "query": user_query,
                    "source": "complex",
                    "llm_reasoning": intent_data.get("reasoning", "")
                }
                
                # 추천, 비교, 분석 작업의 경우 이전 작업 결과 사용 설정
                if task_type in [TaskType.RECOMMENDATION, TaskType.COMPARISON, TaskType.ANALYSIS] and dep_ids:
                    task_data_dict["source"] = "existing"
                
                task = AgentTask(
                    task_id=f"llm_complex_{i+1:03d}",
                    task_type=task_type,
                    description=task_data.get("description", ""),
                    data=task_data_dict,
                    priority=priority,
                    dependencies=dep_ids
                )
                tasks.append(task)
                
            multi_agent_logger.info(f"복합 작업 생성 완료: {[f'{t.task_type.value}({t.task_id})' for t in tasks]}")
            return tasks
            
        except Exception as e:
            multi_agent_logger.error(f"복합 작업 생성 오류: {e}")
            # 폴백으로 단순 작업 생성
            return self._create_simple_task_from_llm(user_query, intent_data, user_id)

    def _analyze_intent_with_keywords(self, user_query: str, user_id: Optional[int] = None) -> List['AgentTask']:
        query_lower = user_query.lower()
        
        # 유사 검색 패턴 우선 확인
        for pattern in self.similarity_search_patterns:
            if re.search(pattern, query_lower):
                multi_agent_logger.info(f"유사 검색 패턴 감지: {pattern}")
                # 기존 검색 결과 확인
                storage_path = os.path.join(tempfile.gettempdir(), "search_history.json")
                has_existing_results = False
                if os.path.exists(storage_path):
                    with open(storage_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    if lines:
                        has_existing_results = True
                
                if has_existing_results:
                    # 기존 결과가 있으면 유사 검색 실행
                    similarity_task = AgentTask(
                        task_id="similarity_search_001",
                        task_type=TaskType.SIMILARITY_SEARCH,
                        description="유사 매물 검색",
                        data={"query": user_query, "source": "existing"},
                        priority=Priority.HIGH
                    )
                    return [similarity_task]
                else:
                    # 기존 결과가 없으면 안내 메시지
                    chat_task = AgentTask(
                        task_id="chat_no_search_for_similarity",
                        task_type=TaskType.CHAT,
                        description="유사 검색 불가 - 검색 결과 없음",
                        data={"query": "유사한 매물을 찾기 위해서는 먼저 매물을 검색해 주세요. 예: '서초구 전세 매물 찾아줘'"},
                        priority=Priority.LOW
                    )
                    return [chat_task]
        
        # 기존 결과에 대한 추천 요청 패턴 우선 확인
        existing_recommendation_patterns = [
            r'이.*중에.*추천',
            r'이.*중에.*좋은',
            r'이.*중에.*괜찮은',
            r'이.*중에.*어떤',
            r'이.*중에.*선택',
            r'이.*중에.*고르',
            r'이.*중.*추천',
            r'이.*중.*좋은',
            r'이.*중.*괜찮은',
            r'여기.*중에.*추천',
            r'여기.*중에.*좋은',
            r'결과.*중에.*추천',
            r'매물.*중에.*추천',
            r'검색.*된.*매물.*중에.*추천',
            r'검색.*결과.*중에.*추천',
            r'검색.*매물.*중에.*추천',
            r'검색.*된.*중에.*추천',
            r'검색.*결과.*추천',
            r'검색.*매물.*추천',
            r'위.*매물.*중에.*추천',
            r'위.*결과.*중에.*추천',
            r'위.*중에.*추천',
            r'현재.*매물.*중에.*추천',
            r'현재.*결과.*중에.*추천',
            r'찾은.*매물.*중에.*추천',
            r'찾은.*결과.*중에.*추천',
            r'.*매물.*중에.*추천',
            r'.*결과.*중에.*추천'
        ]
        
        for pattern in existing_recommendation_patterns:
            if re.search(pattern, query_lower):
                multi_agent_logger.info(f"기존 결과 추천 패턴 감지: {pattern}")
                # 기존 검색 결과가 있는지 임시파일 기준으로 확인
                storage_path = os.path.join(tempfile.gettempdir(), "search_history.json")
                if os.path.exists(storage_path):
                    with open(storage_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    if lines:
                        try:
                            entry = json.loads(lines[-1].strip())
                            results = entry.get("results", [])
                            if isinstance(results, list) and results:
                                recommendation_task = AgentTask(
                                    task_id="recommendation_existing_pattern",
                                    task_type=TaskType.RECOMMENDATION,
                                    description="기존 검색 결과로 추천",
                                    data={"query": user_query, "source": "existing", "properties": results},
                                    priority=Priority.HIGH
                                )
                                return [recommendation_task]
                        except Exception:
                            pass
                # 기존 결과가 없으면 일반 대화로 처리
                chat_task = AgentTask(
                    task_id="chat_no_results",
                    task_type=TaskType.CHAT,
                    description="기존 결과 없음 - 일반 대화",
                    data={"query": user_query},
                    priority=Priority.LOW
                )
                return [chat_task]

        # 지역별 추천 요청 패턴 확인 (예: "반포동에서 괜찮은 매물 추천해줘")
        region_recommendation_patterns = [
            r'([가-힣]+동)에서.*추천',
            r'([가-힣]+동)에서.*좋은',
            r'([가-힣]+동)에서.*괜찮은',
            r'([가-힣]+동).*추천',
            r'([가-힣]+구)에서.*추천',
            r'([가-힣]+구).*추천'
        ]
        
        for pattern in region_recommendation_patterns:
            match = re.search(pattern, query_lower)
            if match:
                region = match.group(1)
                multi_agent_logger.info(f"지역별 추천 패턴 감지: {region}")
                
                # 해당 지역의 기존 검색 결과 확인
                region = extract_location_from_query(user_query)
                storage_path = os.path.join(tempfile.gettempdir(), "search_history.json")
                region_result = None
                if region and os.path.exists(storage_path):
                    with open(storage_path, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                entry = json.loads(line.strip())
                                entry_region = extract_location_from_query(entry.get("query", ""))
                                if entry_region == region and entry.get("results"):
                                    region_result = entry.get("results")
                                    break
                            except Exception:
                                continue
                
                if region_result:
                    # 기존 지역 결과로 추천
                    recommendation_task = AgentTask(
                        task_id="recommendation_existing_region",
                        task_type=TaskType.RECOMMENDATION,
                        description=f"{region} 기존 검색 결과로 추천",
                        data={"query": user_query, "source": "existing", "region": region, "properties": region_result},
                        priority=Priority.HIGH
                    )
                    return [recommendation_task]
                else:
                    # 해당 지역 결과가 없으면 새로 검색 후 추천
                    search_task = AgentTask(
                        task_id="search_rec_001",
                        task_type=TaskType.SEARCH,
                        description=f"{region} 매물 검색",
                        data={"query": user_query, "region": region},
                        priority=Priority.HIGH
                    )
                    recommendation_task = AgentTask(
                        task_id="recommendation_002",
                        task_type=TaskType.RECOMMENDATION,
                        description=f"{region} 검색 결과로 추천",
                        data={"query": user_query, "source": "search", "region": region},
                        dependencies=["search_rec_001"],
                        priority=Priority.MEDIUM
                    )
                    return [search_task, recommendation_task]
        # 기본 키워드 감지
        has_search = any(keyword in query_lower for keyword in self.search_keywords)
        has_analysis = any(keyword in query_lower for keyword in self.analysis_keywords)
        has_recommendation = any(keyword in query_lower for keyword in self.recommendation_keywords)
        has_comparison = any(keyword in query_lower for keyword in self.comparison_keywords)
        has_wishlist = any(keyword in query_lower for keyword in self.wishlist_keywords)
        has_similar_search = any(keyword in query_lower for keyword in self.similar_search_keywords)

        # 검색 + 추천 복합 패턴 (지역별 추천 패턴에서 처리되지 않은 경우)
        if has_search and has_recommendation:
            region = extract_location_from_query(user_query)
            storage_path = os.path.join(tempfile.gettempdir(), "search_history.json")
            region_result = None
            if region and os.path.exists(storage_path):
                with open(storage_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            entry_region = extract_location_from_query(entry.get("query", ""))
                            if entry_region == region and entry.get("results"):
                                region_result = entry.get("results")
                                break
                        except Exception:
                            continue
            
            if region_result:
                recommendation_task = AgentTask(
                    task_id="recommendation_existing_region_search",
                    task_type=TaskType.RECOMMENDATION,
                    description=f"{region} 기존 검색 결과로 추천",
                    data={"query": user_query, "source": "existing", "region": region, "properties": region_result},
                    priority=Priority.HIGH
                )
                return [recommendation_task]
            else:
                search_task = AgentTask(
                    task_id="search_rec_001",
                    task_type=TaskType.SEARCH,
                    description=f"{region} 매물 검색",
                    data={"query": user_query, "region": region},
                    priority=Priority.HIGH
                )
                recommendation_task = AgentTask(
                    task_id="recommendation_002",
                    task_type=TaskType.RECOMMENDATION,
                    description=f"{region} 검색 결과로 추천",
                    data={"query": user_query, "source": "search", "region": region},
                    dependencies=["search_rec_001"],
                    priority=Priority.MEDIUM
                )
                return [search_task, recommendation_task]

        # 기존 결과에 대한 비교 요청 패턴 확인
        existing_comparison_patterns = [
            '이.*중에.*비교',
            '이.*중.*비교',
            r'(\d+)번.*?(\d+)번.*?비교',
            r'(\d+)번.*?(\d+)번.*?차이',
            r'(\d+)번.*?(\d+)번.*?다른',
            r'(\d+)번.*?(\d+)번.*?대비',
            '결과.*비교',
            '매물.*비교',
            '.*?와.*?비교',
            '.*?과.*?비교'
        ]

        for pattern in existing_comparison_patterns:
            if re.search(pattern, query_lower):
                multi_agent_logger.info(f"기존 결과 비교 패턴 감지: {pattern}")
                storage_path = os.path.join(tempfile.gettempdir(), "search_history.json")
                has_existing_results = False
                lines = []
                if os.path.exists(storage_path):
                    with open(storage_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                if lines:
                    try:
                        entry = json.loads(lines[-1].strip())
                        results = entry.get("results", [])
                        if isinstance(results, list) and results:
                            has_existing_results = True
                    except Exception:
                        pass
                if has_existing_results:
                    comparison_task = AgentTask(
                        task_id="comparison_existing",
                        task_type=TaskType.COMPARISON,
                        description="기존 검색 결과 비교",
                        data={"query": user_query, "source": "existing"},
                        priority=Priority.HIGH
                    )
                    return [comparison_task]
                else:
                    # 기존 결과가 없으면 일반 대화로 처리
                    chat_task = AgentTask(
                        task_id="chat_no_results",
                        task_type=TaskType.CHAT,
                        description="기존 결과 없음 - 일반 대화",
                        data={"query": user_query},
                        priority=Priority.LOW
                    )
                    return [chat_task]

        # 기존 결과에 대한 분석 요청 패턴 확인
        for pattern in self.existing_analysis_patterns:
            if re.search(pattern, query_lower):
                multi_agent_logger.info(f"기존 결과 분석 패턴 감지: {pattern}")
                storage_path = os.path.join(tempfile.gettempdir(), "search_history.json")
                has_existing_results = False
                lines = []
                if os.path.exists(storage_path):
                    with open(storage_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                if lines:
                    try:
                        entry = json.loads(lines[-1].strip())
                        results = entry.get("results", [])
                        if isinstance(results, list) and results:
                            has_existing_results = True
                    except Exception:
                        pass
                if has_existing_results:
                    analysis_task = AgentTask(
                        task_id="analysis_existing",
                        task_type=TaskType.ANALYSIS,
                        description="기존 검색 결과 분석",
                        data={"query": user_query, "source": "existing"},
                        priority=Priority.HIGH
                    )
                    return [analysis_task]
                else:
                    # 기존 결과가 없으면 일반 대화로 처리
                    chat_task = AgentTask(
                        task_id="chat_no_results",
                        task_type=TaskType.CHAT,
                        description="기존 결과 없음 - 일반 대화",
                        data={"query": user_query},
                        priority=Priority.LOW
                    )
                    return [chat_task]
        
        # 기존 결과에 대한 추천 요청 패턴 확인 (추가 패턴)
        for pattern in self.existing_recommendation_patterns:
            if re.search(pattern, query_lower):
                multi_agent_logger.info(f"💡 [기존 결과 추천] 패턴 감지 (추가): {pattern}")
                # 기존 검색 결과가 있는지 확인
                storage_path = os.path.join(tempfile.gettempdir(), "search_history.json")
                has_existing_results = False
                if os.path.exists(storage_path):
                    with open(storage_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    if lines:
                        try:
                            entry = json.loads(lines[-1].strip())
                            results = entry.get("results", [])
                            if isinstance(results, list) and results:
                                has_existing_results = True
                        except Exception:
                            pass
                
                if has_existing_results:
                    recommendation_task = AgentTask(
                        task_id="recommendation_existing_additional",
                        task_type=TaskType.RECOMMENDATION,
                        description="기존 검색 결과 추천",
                        data={"query": user_query, "source": "existing"},
                        priority=Priority.HIGH
                    )
                    return [recommendation_task]
                else:
                    # 기존 결과가 없으면 일반 대화로 처리
                    chat_task = AgentTask(
                        task_id="chat_no_results",
                        task_type=TaskType.CHAT,
                        description="기존 결과 없음 - 일반 대화",
                        data={"query": user_query},
                        priority=Priority.LOW
                    )
                    return [chat_task]
        # 기존 키워드 분석 로직 계속
        has_search = any(keyword in query_lower for keyword in self.search_keywords)
        has_analysis = any(keyword in query_lower for keyword in self.analysis_keywords)
        has_recommendation = any(keyword in query_lower for keyword in self.recommendation_keywords)
        has_comparison = any(keyword in query_lower for keyword in self.comparison_keywords)
        has_wishlist = any(keyword in query_lower for keyword in self.wishlist_keywords)
        has_similar_search = any(keyword in query_lower for keyword in self.similar_search_keywords)

        # 나머지 키워드 기반 분석 로직은 기존 _create_tasks_from_basic_analysis 메서드 사용
        return self._create_tasks_from_basic_analysis(
            user_query, user_id,
            has_search, any(keyword in query_lower for keyword in self.analysis_keywords),
            any(keyword in query_lower for keyword in self.wishlist_keywords),
            any(keyword in query_lower for keyword in self.similar_search_keywords),
            has_recommendation,
            any(keyword in query_lower for keyword in self.comparison_keywords)
        )
    
    def _create_tasks_from_basic_analysis(self, user_query: str, user_id: Optional[int] = None, 
                                         has_search: bool = False, has_analysis: bool = False, has_wishlist: bool = False, has_similar_search: bool = False,
                                         has_recommendation: bool = False, has_comparison: bool = False) -> List['AgentTask']:
        """기본 키워드 분석을 기반으로 작업 생성 (LLM 분석 실패 시 폴백)"""
        tasks = []
        
        # 유사 검색 패턴 우선 처리
        if has_similar_search:
            multi_agent_logger.info("🔍 [유사 매물 검색] 패턴 선택")
            similar_search_task = AgentTask(
                task_id="similar_search_001",
                task_type=TaskType.SIMILARITY_SEARCH,
                description="유사 매물 검색",
                data={"query": user_query, "source": "existing"},
                priority=Priority.HIGH
            )
            tasks.append(similar_search_task)
            return tasks
        
        # 특별 패턴: "찾고 + 분석적 요청" 감지
        search_and_analysis_patterns = [
            "찾고.*알려줘", "찾고.*추천", "찾고.*선택", "찾고.*가장", 
            "찾고.*제일", "찾고.*좋은", "찾고.*나쁜", "찾고.*비교"
        ]
        has_search_and_analysis = any(
            re.search(pattern, user_query.lower()) 
            for pattern in search_and_analysis_patterns
        )
        
        if has_search_and_analysis:
            multi_agent_logger.info("🔍+📊 [특별 패턴] 검색+분석 복합 요청")
            has_analysis = True  # 강제로 분석 플래그 설정
        
        # 복잡한 작업 패턴 감지 (검색+비교+추천)
        complex_patterns = [
            "찾아서.*비교.*추천", "찾고.*비교.*추천", "검색.*비교.*추천",
            "찾아서.*추천.*비교", "찾고.*추천.*비교", "검색.*추천.*비교"
        ]
        has_complex_pattern = any(
            re.search(pattern, user_query.lower()) 
            for pattern in complex_patterns
        )
        
        if has_complex_pattern:
            multi_agent_logger.info("🔍+📊 [복잡한 패턴] 검색+비교+추천 복합 요청")
            search_task = AgentTask(
                task_id="search_complex_001",
                task_type=TaskType.SEARCH,
                description="매물 검색 수행",
                data={"query": user_query},
                priority=Priority.HIGH
            )
            tasks.append(search_task)
            
            comparison_task = AgentTask(
                task_id="comparison_001",
                task_type=TaskType.COMPARISON,
                description="검색된 매물 비교",
                data={"query": user_query, "source": "search"},
                dependencies=["search_complex_001"],
                priority=Priority.MEDIUM
            )
            tasks.append(comparison_task)
            
            recommendation_task = AgentTask(
                task_id="recommendation_001",
                task_type=TaskType.RECOMMENDATION,
                description="매물 추천",
                data={"query": user_query, "source": "search"},
                dependencies=["search_complex_001"],
                priority=Priority.MEDIUM
            )
            tasks.append(recommendation_task)
            
            return tasks
        
        # 1. 검색 + 분석 패턴
        if has_search and has_analysis:
            multi_agent_logger.info("🔍+📊 [복합 처리] 검색+분석 패턴")
            search_task = AgentTask(
                task_id="search_001",
                task_type=TaskType.SEARCH,
                description="매물 검색 수행",
                data={"query": user_query},
                priority=Priority.HIGH
            )
            tasks.append(search_task)
            
            analysis_task = AgentTask(
                task_id="analysis_001",
                task_type=TaskType.ANALYSIS,
                description="검색된 매물 분석",
                data={"query": user_query},
                dependencies=["search_001"],
                priority=Priority.MEDIUM
            )
            tasks.append(analysis_task)
        
        # 1-1. 검색 + 추천 패턴
        elif has_search and has_recommendation:
            multi_agent_logger.info("🔍+💡 [복합 처리] 검색+추천 패턴")
            search_task = AgentTask(
                task_id="search_rec_001",
                task_type=TaskType.SEARCH,
                description="매물 검색 수행",
                data={"query": user_query},
                priority=Priority.HIGH
            )
            tasks.append(search_task)
            
            recommendation_task = AgentTask(
                task_id="recommendation_002",
                task_type=TaskType.RECOMMENDATION,
                description="검색된 매물 추천",
                data={"query": user_query, "source": "search"},
                dependencies=["search_rec_001"],
                priority=Priority.MEDIUM
            )
            tasks.append(recommendation_task)
        
        # 1-2. 검색 + 비교 패턴
        elif has_search and has_comparison:
            multi_agent_logger.info("🔍+⚖️ [복합 처리] 검색+비교 패턴")
            search_task = AgentTask(
                task_id="search_comp_001",
                task_type=TaskType.SEARCH,
                description="매물 검색 수행",
                data={"query": user_query},
                priority=Priority.HIGH
            )
            tasks.append(search_task)
            
            comparison_task = AgentTask(
                task_id="comparison_002",
                task_type=TaskType.COMPARISON,
                description="검색된 매물 비교",
                data={"query": user_query, "source": "search"},
                dependencies=["search_comp_001"],
                priority=Priority.MEDIUM
            )
            tasks.append(comparison_task)
        
        # 2. 찜 목록 분석 패턴
        elif has_wishlist and has_analysis:
            multi_agent_logger.info("❤️+📊 [복합 처리] 찜목록+분석 패턴")
            wishlist_task = AgentTask(
                task_id="wishlist_001",
                task_type=TaskType.WISHLIST,
                description="찜 목록 데이터 로드",
                data={"action": "load", "user_id": user_id},
                priority=Priority.HIGH
            )
            tasks.append(wishlist_task)
            
            analysis_task = AgentTask(
                task_id="analysis_002",
                task_type=TaskType.ANALYSIS,
                description="찜 목록 분석",
                data={"query": user_query, "source": "wishlist"},
                dependencies=["wishlist_001"],
                priority=Priority.MEDIUM
            )
            tasks.append(analysis_task)
        
        # 3. 단순 검색 패턴
        elif has_search:
            multi_agent_logger.info("🔍 [단순 검색] 패턴 선택")
            search_task = AgentTask(
                task_id="search_002",
                task_type=TaskType.SEARCH,
                description="매물 검색",
                data={"query": user_query},
                priority=Priority.HIGH
            )
            tasks.append(search_task)
        
        # 4. 단순 추천 패턴 (기존 결과 기반)
        elif has_recommendation:
            multi_agent_logger.info("패턴 선택: 단순 추천 요청")
            # 임시파일에서 기존 검색 결과 확인
            storage_path = os.path.join(tempfile.gettempdir(), "search_history.json")
            has_existing_results = False
            latest_results = None
            
            if os.path.exists(storage_path):
                with open(storage_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                if lines:
                    try:
                        entry = json.loads(lines[-1].strip())
                        results = entry.get("results", [])
                        if isinstance(results, list) and len(results) > 0:
                            has_existing_results = True
                            latest_results = results
                    except Exception:
                        pass
            
            if has_existing_results:
                recommendation_task = AgentTask(
                    task_id="recommendation_003",
                    task_type=TaskType.RECOMMENDATION,
                    description="기존 검색 결과 추천",
                    data={"query": user_query, "source": "existing", "properties": latest_results},
                    priority=Priority.HIGH
                )
                tasks.append(recommendation_task)
            else:
                # 기존 결과가 없으면 일반 대화로 처리
                chat_task = AgentTask(
                    task_id="chat_no_search_results",
                    task_type=TaskType.CHAT,
                    description="검색 결과 없음 - 먼저 검색 요청",
                    data={"query": user_query},
                    priority=Priority.LOW
                )
                tasks.append(chat_task)
                
        # 5. 단순 비교 패턴 (기존 결과 기반)
        elif has_comparison:
            multi_agent_logger.info("패턴 선택: 단순 비교 요청")
            # 임시파일에서 기존 검색 결과 확인
            storage_path = os.path.join(tempfile.gettempdir(), "search_history.json")
            has_existing_results = False
            latest_results = None
            
            if os.path.exists(storage_path):
                with open(storage_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                if lines:
                    try:
                        entry = json.loads(lines[-1].strip())
                        results = entry.get("results", [])
                        if isinstance(results, list) and len(results) >= 2:
                            has_existing_results = True
                            latest_results = results
                    except Exception:
                        pass
            
            if has_existing_results:
                comparison_task = AgentTask(
                    task_id="comparison_003",
                    task_type=TaskType.COMPARISON,
                    description="기존 검색 결과 비교",
                    data={"query": user_query, "source": "existing", "properties": latest_results},
                    priority=Priority.HIGH
                )
                tasks.append(comparison_task)
            else:
                # 기존 결과가 없으면 일반 대화로 처리
                chat_task = AgentTask(
                    task_id="chat_no_comparison_results",
                    task_type=TaskType.CHAT,
                    description="비교할 검색 결과 없음 - 먼저 검색 요청",
                    data={"query": user_query},
                    priority=Priority.LOW
                )
                tasks.append(chat_task)
                
        # 6. 기존 결과 분석 패턴
        elif has_analysis:
            multi_agent_logger.info("패턴 선택: 단순 분석 요청")
            # 임시파일에서 기존 검색 결과 확인
            storage_path = os.path.join(tempfile.gettempdir(), "search_history.json")
            has_existing_results = False
            latest_results = None
            
            if os.path.exists(storage_path):
                with open(storage_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                if lines:
                    try:
                        entry = json.loads(lines[-1].strip())
                        results = entry.get("results", [])
                        if isinstance(results, list) and len(results) > 0:
                            has_existing_results = True
                            latest_results = results
                    except Exception:
                        pass
            
            if has_existing_results:
                analysis_task = AgentTask(
                    task_id="analysis_003",
                    task_type=TaskType.ANALYSIS,
                    description="기존 검색 결과 분석",
                    data={"query": user_query, "source": "existing", "properties": latest_results},
                    priority=Priority.HIGH
                )
                tasks.append(analysis_task)
            else:
                # 기존 결과가 없으면 일반 대화로 처리
                chat_task = AgentTask(
                    task_id="chat_no_analysis_results",
                    task_type=TaskType.CHAT,
                    description="분석할 검색 결과 없음 - 먼저 검색 요청",
                    data={"query": user_query},
                    priority=Priority.LOW
                )
                tasks.append(chat_task)
        
        # 7. 찜 관련 작업
        elif has_wishlist:
            multi_agent_logger.info("❤️ [찜 목록 처리] 패턴 선택")
            wishlist_task = AgentTask(
                task_id="wishlist_002",
                task_type=TaskType.WISHLIST,
                description="찜 목록 처리",
                data={"query": user_query, "user_id": user_id},
                priority=Priority.HIGH
            )
            tasks.append(wishlist_task)
        
        # 8. 일반 대화
        else:
            multi_agent_logger.info("💬 [일반 대화] 패턴 선택")
            chat_task = AgentTask(
                task_id="chat_001",
                task_type=TaskType.CHAT,
                description="일반 대화 처리",
                data={"query": user_query},
                priority=Priority.LOW
            )
            tasks.append(chat_task)
        
        return tasks

# LangChain Tools 정의
@tool
def search_properties_tool(query: str) -> str:
    """
    부동산 매물을 검색하는 도구입니다.
    
    Args:
        query: 사용자의 매물 검색 쿼리 (예: '서초구 전세 2억 이하')
    
    Returns:
        검색 결과에 대한 설명
    """
    search_agent = SearchAgent()
    results = search_agent.search_properties(query)
    return search_agent.format_response(results, query)

@tool
def search_similar_properties_tool(query: str, previous_results: List[dict]) -> str:
    """
    이전 검색 결과를 바탕으로 유사한 매물을 검색하는 도구입니다.
    
    Args:
        query: 유사 검색 요청 (예: '2번 매물과 비슷한 매물 찾아줘')
        previous_results: 이전 검색 결과 리스트
    
    Returns:
        유사 매물 검색 결과에 대한 설명
    """
    try:
        multi_agent_logger.info(f"유사 매물 검색 도구 실행 - 참조 매물 수: {len(previous_results) if previous_results else 0}")
        
        if not previous_results or not isinstance(previous_results, list) or len(previous_results) == 0:
            return "유사한 매물을 찾기 위해서는 먼저 매물을 검색해 주세요."
        
        similarity_agent = SimilaritySearchAgent()
        
        # 참조 매물 식별
        reference_property = similarity_agent._identify_reference_property(query, previous_results)
        
        if not reference_property:
            return "유사 매물 검색을 위한 참조 매물을 찾을 수 없습니다. '1번과 비슷한'과 같이 매물 번호를 명확히 지정해주세요."

        # 참조 매물의 _id를 사용하여 검색
        results = similarity_agent.search_similar_properties(query, previous_results)
        
        if results.get("results"):
            return similarity_agent.format_similarity_response(results, query, reference_property)
        else:
            return results.get("message", "유사한 매물을 찾을 수 없습니다.")
            
    except Exception as e:
        multi_agent_logger.error(f"유사 매물 검색 도구 오류: {str(e)}")
        return f"유사 매물 검색 중 오류가 발생했습니다: {str(e)}"

@tool
def analyze_properties_tool(query: str, properties: List[dict]) -> str:
    """
    부동산 매물을 분석하는 도구입니다.
    
    Args:
        query: 사용자의 분석 요청 (예: '이 매물들 중에 가장 좋은 것은?')
        properties: 분석할 매물 목록
    
    Returns:
        분석 결과에 대한 설명
    """
    try:
        multi_agent_logger.info(f"📊 [분석 도구] 실행 - 매물 수: {len(properties) if properties else 0}")
        multi_agent_logger.info(f"쿼리: {query}")
        
        # 입력값 검증 강화
        if not properties:
            multi_agent_logger.warning("⚠️ [데이터 오류] 매물 목록이 None입니다.")
            return "분석할 매물이 없습니다. 먼저 매물을 검색해주세요."
            
        if not isinstance(properties, list):
            multi_agent_logger.warning(f"⚠️ [데이터 오류] 매물 목록이 리스트가 아닙니다: {type(properties)}")
            return "분석할 매물 데이터 형식이 올바르지 않습니다."
            
        if len(properties) == 0:
            multi_agent_logger.warning("⚠️ [데이터 오류] 매물 목록이 비어있습니다.")
            return "분석할 매물이 없습니다. 먼저 매물을 검색해주세요."
        
        # AnalysisAgent 인스턴스 생성 및 분석 실행
        try:
            analysis_agent = AnalysisAgent()
            
            # 분석 실행
            analysis_result = analysis_agent.analyze(properties, query)
            
            multi_agent_logger.info(f"📊 [분석 성공] 결과 생성 완료 (길이: {len(analysis_result) if analysis_result else 0})")
            return analysis_result
            
        except Exception as analysis_error:
            multi_agent_logger.error(f"🔴 [분석 실행] AnalysisAgent 오류: {str(analysis_error)}")
            return f"매물 분석 중 오류가 발생했습니다: {str(analysis_error)}"
            
    except Exception as e:
        multi_agent_logger.error(f"🔴 [분석 도구] 오류 발생: {str(e)}")
        multi_agent_logger.error(f"🔴 [오류 상세] {traceback.format_exc()}")
        return f"매물 분석 중 오류가 발생했습니다: {str(e)}"

@tool
def recommend_properties_tool(query: str, properties: List[dict]) -> str:
    """
    부동산 매물을 추천하는 도구입니다.
    
    Args:
        query: 사용자의 추천 요청 (예: '가장 좋은 매물 추천해줘')
        properties: 추천할 매물 목록
    
    Returns:
        추천 결과에 대한 설명
    """
    try:
        multi_agent_logger.info(f"💡 [추천 도구] 실행 - 매물 수: {len(properties) if properties else 0}")
        
        if not properties or not isinstance(properties, list) or len(properties) == 0:
            return "추천할 매물이 없습니다. 먼저 매물을 검색해주세요."
        
        recommendation_agent = RecommendationAgent()
        recommendation_result = recommendation_agent.recommend(properties, query)
        
        multi_agent_logger.info(f"💡 [추천 성공] 결과 생성 완료")
        return recommendation_result
        
    except Exception as e:
        multi_agent_logger.error(f"🔴 [추천 도구] 오류 발생: {str(e)}")
        return f"매물 추천 중 오류가 발생했습니다: {str(e)}"

@tool
def compare_properties_tool(query: str, properties: List[dict]) -> str:
    """
    부동산 매물을 비교하는 도구입니다.
    
    Args:
        query: 사용자의 비교 요청 (예: '1번과 3번 매물 비교해줘')
        properties: 비교할 매물 목록
    
    Returns:
        비교 결과에 대한 설명
    """
    try:
        multi_agent_logger.info(f"⚖️ [비교 도구] 실행 - 매물 수: {len(properties) if properties else 0}")
        
        if not properties or not isinstance(properties, list) or len(properties) < 2:
            return "비교할 매물이 2개 이상 필요합니다."
        
        comparison_agent = ComparisonAgent()
        comparison_result = comparison_agent.compare(properties, query)
        
        multi_agent_logger.info(f"⚖️ [비교 성공] 결과 생성 완료")
        return comparison_result
        
    except Exception as e:
        multi_agent_logger.error(f"compare 작업 도구 오류: {str(e)}")
        return f"매물 비교 중 오류가 발생했습니다: {str(e)}"
    
class WishlistToolInput(BaseModel):
    query: str
    user_id: Optional[int]
    action: str = "process"
    search_results: list = None

from langchain.tools import tool

@tool(args_schema=WishlistToolInput)
def wishlist_tool(query: str, user_id: int, action: str = "process", search_results: list = None) -> str:
    """
    찜 목록을 관리하는 도구입니다.
    Args:
        query: 사용자의 찜 관련 요청
        user_id: 사용자 ID
        action: 수행할 작업 유형 (load: 목록 로드, process: 찜 추가/삭제)
        search_results: 최근 검색 결과 리스트
    Returns:
        찜 목록 처리 결과에 대한 설명
    """
    is_view = any(keyword in query.lower() for keyword in ["찜 목록", "찜한 매물", "찜 조회", "찜 비교"])
    is_add = (not is_view) and any(word in query for word in ["찜", "등록", "추가"])
    is_remove = (not is_view) and any(word in query for word in ["삭제", "빼", "제거"])
    if user_id is None or not isinstance(user_id, int) or user_id == 0:
        return "❌ 로그인이 되어있지 않아 찜 기능 사용이 불가능합니다."
    from db.database import get_db
    db = next(get_db())
    wishlist_lam = WishlistLAM()  # LAM 네이밍
    try:
        if action == "load":
            # 찜 목록 로드 로직
            result = get_wishlist(db, user_id)
            if result["result"] == "success" and result.get("data"):
                return f"찜 목록을 로드했습니다. ({len(result.get('data', []))}개 매물)"
            else:
                return "찜 목록이 비어있습니다."
        else:
            # 찜 추가/삭제 처리
            return wishlist_lam.handle_wishlist_request(query, user_id, search_results)
    finally:
        db.close()

@tool
def chat_tool(query: str) -> str:
    """
    일반 대화 응답을 생성하는 도구입니다.
    
    Args:
        query: 사용자 대화 메시지
    
    Returns:
        친근한 대화 응답
    """
    chat_agent = ChatAgent()
    return chat_agent.chat_response(query)

# --- Save Search History Agent & Tool ---

import datetime
import tempfile


class SaveSearchHistoryAgent:
    """
    검색 후 사용자 질의와 매물 정보를 저장하는 에이전트 (임시 파일 사용)
    """
    def __init__(self):
        # OS 임시 디렉토리에 저장 (서버 재시작/새로고침 시 사라짐)
        self.storage_path = os.path.join(tempfile.gettempdir(), "search_history.json")

    def save(self, user_query: str, search_results: list, user_id: int = None):
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "user_id": user_id,
            "query": user_query,
            "results": search_results
        }
        try:
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
            multi_agent_logger.info(f"[SaveSearchHistoryAgent] 저장 완료: {entry}")
            return "검색 기록이 저장되었습니다."
        except Exception as e:
            multi_agent_logger.error(f"[SaveSearchHistoryAgent] 저장 실패: {e}")
            return f"검색 기록 저장 중 오류가 발생했습니다: {e}"

@tool
def save_search_history_tool(user_query: str, search_results: list, user_id: int = None) -> str:
    """
    검색 후 사용자 질의와 매물 정보를 저장하는 도구입니다.
    Args:
        user_query: 사용자의 검색 질의
        search_results: 검색된 매물 정보 리스트
        user_id: 사용자 ID (선택)
    Returns:
        저장 결과 메시지
    """
    agent = SaveSearchHistoryAgent()
    return agent.save(user_query, search_results, user_id)

class EnhancedMultiAgentOrchestrator:
    """향상된 다중 에이전트 오케스트레이터 (LangChain 기반)"""
    
    def __init__(self):
        # LangChain 구성 요소
        self.llm = self._create_llm(temperature=0.2)

        # 서버 시작 시 임시 검색 기록 파일 초기화
        temp_path = os.path.join(tempfile.gettempdir(), "search_history.json")
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                multi_agent_logger.info(f"[초기화] search_history.json 파일을 삭제했습니다: {temp_path}")
            else:
                multi_agent_logger.info(f"[초기화] search_history.json 파일이 존재하지 않아 삭제하지 않았습니다: {temp_path}")
        except Exception as e:
            multi_agent_logger.error(f"[초기화] search_history.json 파일 삭제 실패: {e}")

        # 메모리 설정
        self.memory = self._create_memory()

        # 기본 에이전트들
        self.search_agent = SearchAgent()
        self.similarity_search_agent = SimilaritySearchAgent()
        self.analysis_agent = AnalysisAgent()
        self.recommendation_agent = RecommendationAgent()
        self.comparison_agent = ComparisonAgent()
        self.chat_agent = ChatAgent()
        self.wishlist_lam = WishlistLAM()  # LAM 네이밍 (변경)
        # 작업 관리
        self.task_parser = TaskParser()
        self.task_parser.llm = self.llm  # TaskParser에 LLM 설정
        self.active_tasks: Dict[str, AgentTask] = {}
        self.completed_tasks: Dict[str, AgentTask] = {}

        # 세션 히스토리 (대화만을 위한 간단한 히스토리)
        self.session_history: List[Dict[str, Any]] = []

        # LangChain 도구들
        self.tools = [
            search_properties_tool,
            search_similar_properties_tool,
            analyze_properties_tool,
            recommend_properties_tool,
            compare_properties_tool,
            wishlist_tool,
            chat_tool
            ,save_search_history_tool
        ]

        # 에이전트 프롬프트
        self.agent_prompt = ChatPromptTemplate.from_messages([
            ("system", """
            당신은 HouseAI의 똑똑한 부동산 에이전트입니다.
            사용자의 부동산 관련 질문과 요청을 처리하기 위해 다양한 도구를 활용할 수 있습니다.
            
            사용 가능한 도구들:
            {tools}
            
            도구 이름: {tool_names}
            
            부동산 매물은 다음과 같은 구조를 가집니다 (PropertyItem):
            - _id: 매물 고유 ID
            - gu, dong: 구, 동 정보
            - aptNm: 아파트명
            - area_pyeong: 평수 정보
            - deposit, monthlyRent: 보증금, 월세 (문자열 형태)
            - rent_type: 거래 유형 (전세/월세)
            - nearest_station: 가장 가까운 지하철역
            - distance_to_station: 역까지의 거리 (미터)
            - lat, lng: 위도, 경도 좌표
            
            최적의 결과를 위해 도구들을 조합하여 사용하세요.
            """),
            ("human", "{input}"),
            ("ai", "{agent_scratchpad}")
        ])

        # 에이전트 생성
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            self.agent_prompt
        )

        # 에이전트 실행기 생성
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True
        )
    
    def load_search_history_from_tempfile(self):
        """임시 파일에서 검색 기록을 로드"""
        storage_path = os.path.join(tempfile.gettempdir(), "search_history.json")
        results = []
        if os.path.exists(storage_path):
            with open(storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        results.append({
                            "query": entry.get("query"),
                            "location": extract_location_from_query(entry.get("query", "")),
                            "result": {"results": entry.get("results", []), "total_count": len(entry.get("results", []))}
                        })
                    except Exception:
                        continue
        return results
    
    @staticmethod
    def _create_llm(temperature: float = 0.2, model: str = "auto"):
        """통일된 LLM 설정을 위한 공통 메서드 - Claude와 OpenAI 지원"""
        # API 키 확인
        has_anthropic_key = bool(os.getenv("ANTHROPIC_API_KEY"))
        has_openai_key = bool(os.getenv("OPENAI_API_KEY"))
        
        print(f"🔑 API Keys - Anthropic: {has_anthropic_key}, OpenAI: {has_openai_key}")
        print(f"📦 Claude Available: {CLAUDE_AVAILABLE}")
        
        # 모델 자동 선택
        if model == "auto":
            if CLAUDE_AVAILABLE and has_anthropic_key:
                model = "claude-3-5-sonnet-20241022"
                print("🤖 Using Claude 3.5 Sonnet")
            elif has_openai_key:
                model = "gpt-4"
                print("🤖 Using GPT-4")
            else:
                raise ValueError("❌ No valid API keys found. Please set ANTHROPIC_API_KEY or OPENAI_API_KEY")
        
        # Claude 모델 사용
        if model.startswith("claude"):
            if CLAUDE_AVAILABLE and has_anthropic_key:
                try:
                    llm = ChatAnthropic(
                        model=model,
                        temperature=temperature,
                        api_key=os.getenv("ANTHROPIC_API_KEY"),
                        max_tokens=2048,
                        timeout=30.0,
                        max_retries=3
                    )
                    print(f"✅ Claude LLM created successfully: {model}")
                    return llm
                except Exception as e:
                    print(f"❌ Claude LLM creation failed: {e}")
                    if has_openai_key:
                        print("🔄 Falling back to OpenAI GPT-4")
                        model = "gpt-4"
                    else:
                        raise
            else:
                if has_openai_key:
                    print("🔄 Claude not available, using OpenAI GPT-4")
                    model = "gpt-4"
                else:
                    raise ValueError("❌ Claude requested but not available, and no OpenAI key found")
        
        # OpenAI 모델 사용 (기본값 또는 폴백)
        if has_openai_key:
            try:
                llm = ChatOpenAI(
                    model=model,
                    temperature=temperature,
                    api_key=os.getenv("OPENAI_API_KEY"),
                    max_tokens=2048,
                    timeout=30.0,
                    max_retries=3
                )
                print(f"✅ OpenAI LLM created successfully: {model}")
                return llm
            except Exception as e:
                print(f"❌ OpenAI LLM creation failed: {e}")
                raise
        else:
            raise ValueError(f"❌ Model {model} requested but no OpenAI API key available")
    
    def _create_memory(self) -> ConversationBufferMemory:
        """메모리 설정"""
        return ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="output",
            input_key="input",
            max_token_limit=4096
        )
    
    def _manage_memory_size(self):
        """메모리 크기 관리"""
        try:
            if hasattr(self.memory, 'chat_memory') and hasattr(self.memory.chat_memory, 'messages'):
                messages = self.memory.chat_memory.messages
                if len(messages) > 100:  # 100개 이상 메시지 시 정리
                    self.memory.chat_memory.messages = messages[-20:]  # 최근 20개만 유지
        except Exception as e:
            multi_agent_logger.error(f"메모리 관리 중 오류: {e}")
    
    def get_memory_summary(self) -> Dict[str, Any]:
        """현재 메모리 상태 요약"""
        try:
            if hasattr(self.memory, 'chat_memory') and hasattr(self.memory.chat_memory, 'messages'):
                messages = self.memory.chat_memory.messages
                return {
                    "total_messages": len(messages),
                    "last_message_preview": str(messages[-1])[:100] + "..." if messages else "빈 메모리"
                }
            return {"total_messages": 0, "last_message_preview": "메모리 없음"}
        except Exception as e:
            return {"error": f"메모리 상태 확인 실패: {e}"}
    
    def _handle_error(self, error: Exception, context: Dict[str, Any], task_type: str = "general") -> Dict[str, Any]:
        """표준화된 에러 처리"""
        
        error_message = str(error)
        error_type = type(error).__name__
        
        # 상세 로깅
        multi_agent_logger.error(f"{task_type} 에러 발생: {error_type} - {error_message}")
        multi_agent_logger.error(f"에러 컨텍스트: {context}")
        
        # 심각한 오류인 경우 추가 로깅
        if error_type in ["AttributeError", "TypeError", "KeyError"]:
            multi_agent_logger.error(f"심각한 오류 상세 정보:\n{traceback.format_exc()}")
        
        # 사용자 친화적 메시지 생성
        if error_type == "ConnectionError":
            user_message = "서버 연결에 문제가 있습니다. 잠시 후 다시 시도해주세요."
        elif error_type == "TimeoutError":
            user_message = "요청 처리 시간이 초과되었습니다. 다시 시도해주세요."
        elif "API" in error_message or "openai" in error_message.lower():
            user_message = "AI 서비스에 일시적인 문제가 있습니다. 잠시 후 다시 시도해주세요."
        else:
            user_message = f"요청 처리 중 문제가 발생했습니다. 다시 시도해주세요."
        
        return {
            "reply": user_message,
            "agents_used": ["ERROR_HANDLER"],
            "search_results": {},
            "results": [],
            "type": "error",
            "error_details": {
                "type": error_type,
                "message": error_message,
                "context": context,
                "task_type": task_type
            }
        }
    
    async def execute_task(self, task: AgentTask) -> AgentTask:
        """개별 작업 실행 (LangChain 도구 활용) - 우선순위 2 개선"""
        from services.agents.utils import multi_agent_logger
        
        start_time = time.time()
        
        try:
            multi_agent_logger.log_agent_start(
                f"{task.task_type.value.upper()}Agent", 
                task.task_type.value, 
                task.data.get("query", "")
            )
            
            task.status = "running"
            
            # 작업별 타임아웃 설정 (성능 최적화)
            timeout_config = {
                TaskType.SEARCH: 15.0,
                TaskType.SIMILARITY_SEARCH: 20.0,
                TaskType.ANALYSIS: 10.0,
                TaskType.RECOMMENDATION: 12.0,
                TaskType.COMPARISON: 12.0,
                TaskType.WISHLIST: 5.0,
                TaskType.CHAT: 8.0
            }
            
            timeout = timeout_config.get(task.task_type, 10.0)
            
            # 타임아웃 내에서 작업 실행
            completed_task = await asyncio.wait_for(
                self._execute_task_internal(task), 
                timeout=timeout
            )
            
            duration = time.time() - start_time
            multi_agent_logger.log_agent_end(
                f"{task.task_type.value.upper()}Agent",
                task.task_type.value,
                duration,
                completed_task.status == "completed"
            )
            
            return completed_task
            
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            task.status = "failed"
            task.error = f"작업 타임아웃 ({timeout}초 초과)"
            multi_agent_logger.log_agent_end(
                f"{task.task_type.value.upper()}Agent",
                task.task_type.value,
                duration,
                False
            )
            task.result = {"error": str(task.error), "response": f"작업 실행 중 타임아웃이 발생했습니다 ({timeout}초 초과)"}
            return task
        except Exception as e:
            duration = time.time() - start_time
            task.status = "failed"
            task.error = str(e)
            multi_agent_logger.log_error(f"{task.task_type.value.upper()}Agent", e, {"task_id": task.task_id})
            task.result = {"error": str(e), "response": f"작업 실행 중 오류가 발생했습니다: {str(e)}"}
            return task
    
    async def _execute_task_internal(self, task: AgentTask) -> AgentTask:
        # ============= [SEARCH] ==============
        if task.task_type == TaskType.SEARCH:
            query = task.data.get("query", "")
            search_type = task.data.get("search_type", "normal")

            # location 추출 (동/역/구 모두 인식)
            location = extract_location_from_query(query)

            if search_type == "similar":                # 기존 로직 사용 (유사 매물 검색 등)
                pass
            else:
                try:
                    search_results = self.search_agent.search_properties(query)
                    response = self.search_agent.format_response(search_results, query)
                except Exception as e:
                    multi_agent_logger.error(f"일반 검색 실행 오류: {str(e)}")
                    search_results = {"results": [], "total_count": 0}
                    response = f"검색 중 오류가 발생했습니다: {str(e)}"

            # --- [추가] 검색 결과 저장 및 경로/성공여부 로그 ---
            from services.enhanced_multi_agent_service import save_search_history_tool
            temp_path = os.path.join(tempfile.gettempdir(), "search_history.json")
            save_args = {   
                "user_query": query,
                "search_results": search_results.get("results", [])
            }
            # user_id는 task.data에서 가져오거나 생략
            if task.data.get("user_id") is not None:
                save_args["user_id"] = task.data.get("user_id")
            save_msg = save_search_history_tool.invoke(save_args)
            multi_agent_logger.info(f"[DEBUG] search_history.json 저장 경로: {temp_path}")
            multi_agent_logger.info(f"[DEBUG] 저장 함수 반환 메시지: {save_msg}")

            task.result = {
                "search_results": search_results,
                "response": response,
                "save_history_path": temp_path,
                "save_history_msg": save_msg
            }

        # ============= [SIMILARITY_SEARCH] ==============
        elif task.task_type == TaskType.SIMILARITY_SEARCH:
            query = task.data.get("query", "")
            source = task.data.get("source", "existing")
            
            try:
                # 임시 파일에서 기존 검색 결과 로드
                search_history = self.load_search_history_from_tempfile()
                
                if not search_history:
                    # 기존 검색 결과가 없는 경우
                    response = "유사한 매물을 찾기 위해서는 먼저 매물을 검색해 주세요. 예: '서초구 전세 매물 찾아줘'"
                    similarity_results = {"results": [], "total_count": 0}
                else:
                    # 가장 최근 검색 결과 사용
                    last_search = search_history[-1]
                    reference_properties = last_search["result"].get("results", [])
                    
                    if not reference_properties:
                        response = "참조할 수 있는 매물이 없습니다. 먼저 매물을 검색해 주세요."
                        similarity_results = {"results": [], "total_count": 0}
                    else:
                        # 유사 매물 검색 실행
                        similarity_results = self.similarity_search_agent.search_similar_properties(query, reference_properties)
                        
                        # 참조 매물 식별 및 응답 포맷팅
                        reference_property = self.similarity_search_agent._identify_reference_property(query, reference_properties)
                        if reference_property and similarity_results.get("results"):
                            response = self.similarity_search_agent.format_similarity_response(similarity_results, query, reference_property)
                        else:
                            response = similarity_results.get("message", "유사한 매물을 찾을 수 없습니다.")
                
                # 유사 검색 결과도 임시 파일에 저장
                if similarity_results.get("results"):
                    temp_path = os.path.join(tempfile.gettempdir(), "search_history.json")
                    entry = {
                        "timestamp": datetime.datetime.now().isoformat(),
                        "user_id": None,  # user_id는 필요시 별도로 추가
                        "query": query,
                        "results": similarity_results.get("results", [])
                    }
                    try:
                        with open(temp_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    except Exception as e:
                        multi_agent_logger.error(f"유사 검색 결과 저장 오류: {e}")
                
                task.result = {
                    "search_results": similarity_results,
                    "response": response
                }
                
            except Exception as e:
                multi_agent_logger.error(f"유사 매물 검색 실행 오류: {str(e)}")
                task.result = {
                    "search_results": {"results": [], "total_count": 0},
                    "response": f"유사 매물 검색 중 오류가 발생했습니다: {str(e)}"
                }

        # ============= [ANALYSIS] ==============
        elif task.task_type == TaskType.ANALYSIS:
            query = task.data.get("query", "")
            source = task.data.get("source", "search")
            properties = task.data.get("properties")  # 직접 전달된 속성들
            
            try:
                analysis_data = None
                if properties and isinstance(properties, list) and len(properties) > 0:
                    # 직접 전달된 속성들 사용
                    analysis_data = {"results": properties, "total_count": len(properties)}
                    multi_agent_logger.info(f"직접 전달된 {len(properties)}개 매물로 분석 실행")
                elif source == "wishlist":
                    # 찜 목록 기반 분석 - DB에서 직접 로드
                    user_id = task.data.get("user_id")
                    if user_id:
                        from db.database import get_db
                        db = next(get_db())
                        try:
                            wishlist_data = get_wishlist(db, user_id)
                            analysis_data = wishlist_data
                        except Exception as e:
                            multi_agent_logger.error(f"찜 목록 로드 오류: {str(e)}")
                            analysis_data = {"results": [], "total_count": 0}
                        finally:
                            db.close()
                    else:
                        analysis_data = {"results": [], "total_count": 0}
                else:
                    # search_history.json에서 검색 결과 로드 (load_search_history_from_tempfile 함수 사용)
                    search_history = self.load_search_history_from_tempfile()
                    
                    if source == "existing":
                        refs = resolve_references(query, search_history)
                        if refs:
                            analysis_data = {"results": refs, "total_count": len(refs)}
                        elif search_history:
                            last_result = search_history[-1]
                            analysis_data = {"results": last_result.get("result", {}).get("results", []), "total_count": len(last_result.get("result", {}).get("results", []))}
                        else:
                            analysis_data = {"results": [], "total_count": 0}
                    else:
                        if search_history:
                            last_result = search_history[-1]
                            analysis_data = {"results": last_result.get("result", {}).get("results", []), "total_count": len(last_result.get("result", {}).get("results", []))}
                        else:
                            analysis_data = {"results": [], "total_count": 0}
                            
                properties_to_analyze = analysis_data.get("results", [])
                if not properties_to_analyze:
                    response = "분석할 매물이 없습니다. 먼저 매물을 검색하거나 찜 목록을 불러와주세요."
                elif not isinstance(properties_to_analyze, list):
                    response = "매물 데이터 형식이 올바르지 않습니다."
                else:
                    valid_properties = [prop for prop in properties_to_analyze if isinstance(prop, dict)]
                    if not valid_properties:
                        response = "분석할 유효한 매물이 없습니다."
                    else:
                        try:
                            response = self.analysis_agent.analyze(valid_properties, query)
                            multi_agent_logger.info(f"분석 완료: {len(valid_properties)}개 매물 분석")
                        except Exception as e:
                            multi_agent_logger.error(f"분석 실행 오류: {str(e)}")
                            response = f"매물 분석 중 오류가 발생했습니다: {str(e)}"
                task.result = {
                    "analysis_response": response,
                    "analyzed_data": analysis_data
                }
            except Exception as e:
                multi_agent_logger.error(f"분석 작업 실행 오류: {str(e)}")
                task.result = {
                    "analysis_response": f"매물 분석 중 오류가 발생했습니다: {str(e)}",
                    "analyzed_data": {"results": [], "total_count": 0}
                }
        # ============= [COMPARISON] ==============
        elif task.task_type == TaskType.COMPARISON:
            query = task.data.get("query", "")
            source = task.data.get("source", "search")
            properties = task.data.get("properties")  # 직접 전달된 속성들
            
            try:
                properties_to_compare = []
                if properties and isinstance(properties, list) and len(properties) >= 2:
                    # 직접 전달된 속성들 사용
                    properties_to_compare = properties
                    multi_agent_logger.info(f"직접 전달된 {len(properties)}개 매물로 비교 실행")
                elif source == "wishlist":
                    # 찜 목록 기반 비교 - DB에서 직접 로드
                    user_id = task.data.get("user_id")
                    if user_id:
                        from db.database import get_db
                        db = next(get_db())
                        try:
                            wishlist_data = get_wishlist(db, user_id)
                            properties_to_compare = wishlist_data.get("results", [])
                        except Exception as e:
                            multi_agent_logger.error(f"찜 목록 로드 오류: {str(e)}")
                            properties_to_compare = []
                        finally:
                            db.close()
                    else:
                        properties_to_compare = []
                else:
                    # search_history.json에서 검색 결과 로드 (load_search_history_from_tempfile 함수 사용)
                    search_history = self.load_search_history_from_tempfile()
                    
                    refs = resolve_references(query, search_history)
                    if refs and len(refs) >= 2:
                        properties_to_compare = refs
                    elif search_history:
                        last_result = search_history[-1]
                        properties_to_compare = last_result.get("result", {}).get("results", [])
                        
                # 비교할 데이터가 있는지 확인
                if not properties_to_compare or len(properties_to_compare) < 2:
                    response = "비교할 매물이 2개 이상 필요합니다. 각각의 검색 결과에서 1개 이상 매물이 필요합니다."
                elif not all(isinstance(p, dict) for p in properties_to_compare):
                    response = "매물 데이터 형식이 올바르지 않습니다."
                else:
                    try:
                        response = self.comparison_agent.compare(properties_to_compare, query)
                        multi_agent_logger.info(f"비교 완료: {len(properties_to_compare)}개 매물 비교")
                    except Exception as e:
                        multi_agent_logger.error(f"비교 실행 오류: {str(e)}")
                        response = f"매물 비교 중 오류가 발생했습니다: {str(e)}"

                task.result = {
                    "comparison_response": response,
                    "compared_properties": properties_to_compare
                }
            except Exception as e:
                multi_agent_logger.error(f"비교 작업 실행 오류: {str(e)}")
                task.result = {
                    "comparison_response": f"매물 비교 중 오류가 발생했습니다: {str(e)}",
                    "compared_properties": []
                }

        elif task.task_type == TaskType.WISHLIST:
            # LangChain 기반 찜 목록 도구 실행
            query = task.data.get("query", "")
            user_id = task.data.get("user_id")
            action = task.data.get("action", "process")
            
            if action == "load":
                # 찜 목록 로드
                if user_id:
                    # 도구를 통한 찜 목록 데이터 로드
                    from db.database import get_db
                    db = next(get_db())
                    try:
                        wishlist_result = get_wishlist(db, user_id)
                        if wishlist_result["result"] == "success" and wishlist_result.get("data"):
                            wishlist_data = {
                                "results": wishlist_result["data"],
                                "total_count": len(wishlist_result["data"])
                            }
                        else:
                            wishlist_data = {"results": [], "total_count": 0}
                    finally:
                        db.close()
                    
                    task.result = {
                        "wishlist_data": wishlist_data,
                        "response": f"찜 목록을 로드했습니다. ({len(wishlist_data.get('results', []))}개 매물)"
                    }
                else:
                    task.result = {
                        "response": "로그인이 필요합니다.",
                        "wishlist_data": {"results": [], "total_count": 0}
                    }
            else:
                # 일반 찜 처리
                # 최신 검색 결과를 search_history.json에서 직접 읽어옴
                storage_path = os.path.join(tempfile.gettempdir(), "search_history.json")
                search_results = {"results": [], "total_count": 0}
                if os.path.exists(storage_path):
                    with open(storage_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    if lines:
                        try:
                            entry = json.loads(lines[-1].strip())
                            search_results = {"results": entry.get("results", []), "total_count": len(entry.get("results", []))}
                        except Exception:
                            pass
                response = wishlist_tool({
                    "query": query,
                    "user_id": user_id,
                    "action": action,
                    "search_results": search_results["results"]
                })
                task.result = {
                    "response": response,
                    "search_results": search_results
                }
        elif task.task_type == TaskType.RECOMMENDATION:
            # LangChain 기반 추천 도구 실행
            query = task.data.get("query", "")
            source = task.data.get("source", "search")
            
            try:
                # 데이터 소스 확인 및 설정
                if source == "wishlist":
                    # 찜 목록 기반 추천 - DB에서 직접 로드
                    user_id = task.data.get("user_id")
                    if user_id:
                        from db.database import get_db
                        db = next(get_db())
                        try:
                            wishlist_data = get_wishlist(db, user_id)
                            properties = wishlist_data.get("results", [])
                        except Exception as e:
                            multi_agent_logger.error(f"찜 목록 로드 오류: {str(e)}")
                            properties = []
                        finally:
                            db.close()
                    else:
                        properties = []
                elif source == "existing":
                    # 기존 검색 결과 추천 - task.data에서 properties 직접 사용하거나 search_history에서 로드
                    properties = task.data.get("properties", [])
                    if not properties:
                        # load_search_history_from_tempfile 함수 사용
                        search_history = self.load_search_history_from_tempfile()
                        if search_history:
                            last_result = search_history[-1]
                            properties = last_result.get("result", {}).get("results", [])
                        else:
                            properties = []
                else:
                    # 새로운 검색 결과 추천 - search_history에서 가장 최근 결과 사용
                    search_history = self.load_search_history_from_tempfile()
                    properties = []
                    if search_history:
                        last_result = search_history[-1]
                        properties = last_result.get("result", {}).get("results", [])

                # 이제 properties는 반드시 List[dict] 형태
                if not properties:
                    response = "추천할 매물이 없습니다. 먼저 매물을 검색해주세요."
                elif not isinstance(properties, list):
                    response = "매물 데이터 형식이 올바르지 않습니다."
                else:
                    # 유효한 데이터만 필터링
                    valid_properties = [prop for prop in properties if isinstance(prop, dict)]
                    
                    if not valid_properties:
                        response = "추천할 유효한 매물이 없습니다."
                    else:
                        # RecommendationAgent를 사용하여 추천 실행
                        try:
                            recommendation_agent = self.recommendation_agent
                            response = recommendation_agent.recommend(valid_properties, query)
                        except Exception as e:
                            multi_agent_logger.error(f"추천 실행 오류: {str(e)}")
                            response = f"매물 추천 중 오류가 발생했습니다: {str(e)}"

                task.result = {
                    "recommendation_response": response,
                    "recommendation_data": {"results": properties, "total_count": len(properties)}
                }
            except Exception as e:
                multi_agent_logger.error(f"추천 작업 실행 오류: {str(e)}")
                task.result = {
                    "recommendation_response": f"매물 추천 중 오류가 발생했습니다: {str(e)}",
                    "recommendation_data": {"results": [], "total_count": 0}
                }
        elif task.task_type == TaskType.CHAT:
            # LangChain 기반 채팅 도구 실행 (이전 대화 기록 포함)
            query = task.data.get("query", "")
            
            # 미리 정의된 응답이 있는지 확인
            predefined_response = task.data.get("response")
            if predefined_response:
                # 위치 재질문 등 특별한 응답이 미리 정의된 경우
                response = predefined_response
                multi_agent_logger.info(f"미리 정의된 응답 사용: {response}")
            else:
                # 일반 채팅 응답 생성
                # session_history를 OpenAI messages 포맷으로 변환
                history = []
                for h in self.session_history:
                    if "role" in h and "content" in h:
                        history.append({"role": h["role"], "content": h["content"]})
                    elif "user" in h:
                        history.append({"role": "user", "content": h["user"]})
                    elif "assistant" in h:
                        history.append({"role": "assistant", "content": h["assistant"]})
                response = self.chat_agent.chat_response(query, history=history)
            
            # 대화 기록에 이번 turn 추가
            self.session_history.append({"role": "user", "content": query})
            self.session_history.append({"role": "assistant", "content": response})
            task.result = {
                "response": response
            }
        
        task.status = "completed"
        return task
    
    def check_dependencies(self, task: AgentTask) -> bool:
        """작업의 의존성 확인 (LangChain Agent 작업 관리)"""
        for dep_id in task.dependencies:
            if dep_id not in self.completed_tasks:
                return False
            if self.completed_tasks[dep_id].status != "completed":
                return False
        return True
    
    async def process_user_message(self, user_query: str, user_id: Optional[int] = None) -> Dict[str, Any]:
        """사용자 메시지를 다중 에이전트로 처리 (LangChain Agent 기반)"""
        try:
            multi_agent_logger.info(f"Enhanced Multi-Agent 처리 시작: '{user_query}'")
            # 메모리 관리 - 처리 시작 전
            self._manage_memory_size()
            memory_info = self.get_memory_summary()
            multi_agent_logger.info(f"현재 메모리 상태: {memory_info['total_messages']}개 메시지")
            # 에러 처리 표준화를 위한 컨텍스트 설정
            error_context = {
                "user_id": user_id,
                "query": user_query,
                "timestamp": __import__('datetime').datetime.now().isoformat()
            }
            # 1. 사용자 요청을 작업들로 분해 (user_id를 직접 전달)
            tasks = self.task_parser.parse_user_request(user_query, user_id)
            multi_agent_logger.info(f"🔢 [작업 생성] 총 {len(tasks)}개 작업 생성")
            multi_agent_logger.info(f"작업 세부 정보: {[task.task_id for task in tasks]}")
            
            # 모든 작업에 user_id 추가
            for task in tasks:
                if "user_id" not in task.data:
                    task.data["user_id"] = user_id
            # 2. 작업 스케줄링 및 실행
            pending_tasks = {task.task_id: task for task in tasks}
            completed_results = []
            while pending_tasks:
                # 실행 가능한 작업 찾기 (의존성이 없거나 의존성이 완료된 작업)
                ready_tasks = [
                    task for task in pending_tasks.values()
                    if self.check_dependencies(task)
                ]
                if not ready_tasks:
                    multi_agent_logger.warning("⚠️ [작업 스케줄링] 순환 의존성 또는 실행 불가능한 작업 발견")
                    break
                # 3. 병렬 실행 (우선순위 고려)
                ready_tasks.sort(key=lambda t: t.priority.value)
                # 병렬로 실행할 작업들 (의존성이 없는 작업들)
                parallel_tasks = [task for task in ready_tasks if not task.dependencies]
                sequential_tasks = [task for task in ready_tasks if task.dependencies]
                # 병렬 실행
                if parallel_tasks:
                    multi_agent_logger.info(f"🔄 [병렬 실행] 작업: {[t.task_id for t in parallel_tasks]}")
                    parallel_results = await asyncio.gather(
                        *[self.execute_task(task) for task in parallel_tasks],
                        return_exceptions=True
                    )
                    for result in parallel_results:
                        if isinstance(result, AgentTask):
                            self.completed_tasks[result.task_id] = result
                            completed_results.append(result)
                            pending_tasks.pop(result.task_id, None)
                # 순차 실행 (의존성이 있는 작업들)
                for task in sequential_tasks:
                    if self.check_dependencies(task):
                        multi_agent_logger.info(f"📝 [순차 실행] 작업: {task.task_id}")
                        completed_task = await self.execute_task(task)
                        self.completed_tasks[completed_task.task_id] = completed_task
                        completed_results.append(completed_task)
                        pending_tasks.pop(completed_task.task_id, None)
            # 4. 결과 통합 및 응답 생성
            return self._combine_results(completed_results, user_query)
        except Exception as e:
            # 표준화된 에러 처리 사용
            return self._handle_error(e, error_context, "enhanced_multi_agent")
    
    def _combine_results(self, completed_tasks: List[AgentTask], user_query: str) -> Dict[str, Any]:
        """여러 에이전트의 결과를 통합 (LangChain 도구 출력 처리)"""
        
        agents_used = list(set([task.task_type.value.upper() for task in completed_tasks]))
        combined_response = []
        final_search_results = {}
        result_type = "chat"
        search_results_set = False  # 검색 결과가 한 번 설정되었는지 추적
        
        # 우선순위에 따라 정렬 (검색 -> 유사검색 -> 추천 -> 비교 -> 분석 -> 찜 -> 채팅)
        task_order = {
            TaskType.SEARCH: 1,
            TaskType.SIMILARITY_SEARCH: 2,
            TaskType.RECOMMENDATION: 3,  # 추천을 분석/비교보다 먼저
            TaskType.COMPARISON: 4,
            TaskType.ANALYSIS: 5,
            TaskType.WISHLIST: 6,
            TaskType.CHAT: 7
        }
        
        completed_tasks.sort(key=lambda t: task_order.get(t.task_type, 5))
        
        for task in completed_tasks:
            multi_agent_logger.info(f"✅ [작업 완료] {task.task_id} - 상태: {task.status}")
            
            if task.status == "completed" and task.result:
                
                if task.task_type == TaskType.SEARCH:
                    search_results = task.result.get("search_results", {})
                    response = task.result.get("response", "")
                    
                    multi_agent_logger.info(f"검색 결과 처리 - 결과 수: {len(search_results.get('results', []))}")
                    multi_agent_logger.info(f"검색 응답 길이: {len(response)}")
                    
                    # 첫 번째 검색 결과만 설정
                    if not search_results_set and search_results.get("results"):
                        final_search_results = search_results
                        search_results_set = True
                    
                    if search_results.get("results") or response:
                        result_type = "search_result"
                        if response:
                            # 검색 결과 섹션 헤더 추가
                            combined_response.append(f"🔍 **매물 검색 결과**\n\n{response}")
                        else:
                            combined_response.append("🔍 **매물 검색 결과**\n\n검색이 완료되었습니다.")
                    else:
                        combined_response.append("🔍 **매물 검색 결과**\n\n검색 결과가 없습니다.")
                
                elif task.task_type == TaskType.SIMILARITY_SEARCH:
                    search_results = task.result.get("search_results", {})
                    response = task.result.get("response", "")
                    
                    multi_agent_logger.info(f"유사 검색 결과 처리 - 결과 수: {len(search_results.get('results', []))}")
                    multi_agent_logger.info(f"유사 검색 응답 길이: {len(response)}")
                    
                    # 첫 번째 검색 결과만 설정
                    if not search_results_set and search_results.get("results"):
                        final_search_results = search_results
                        search_results_set = True
                    
                    if search_results.get("results") or response:
                        result_type = "search_result"
                        if response:
                            # 유사 검색 결과 섹션 헤더 추가
                            combined_response.append(f"🔍 **유사 매물 검색 결과**\n\n{response}")
                        else:
                            combined_response.append("🔍 **유사 매물 검색 결과**\n\n유사 매물 검색이 완료되었습니다.")
                    else:
                        combined_response.append("🔍 **유사 매물 검색 결과**\n\n유사한 매물을 찾을 수 없습니다.")
                
                elif task.task_type == TaskType.RECOMMENDATION:
                    recommendation_response = task.result.get("recommendation_response", "")
                    recommendation_data = task.result.get("recommendation_data", {})
                    
                    # 추천 작업에서는 매물 데이터 설정하지 않고 텍스트 응답만 추가
                    # 단, 첫 번째 검색 결과가 아직 설정되지 않은 경우에만 설정
                    if not search_results_set and recommendation_data.get("results"):
                        final_search_results = recommendation_data
                        result_type = "search_result"
                        search_results_set = True
                    
                    # 추천 결과 섹션 헤더 추가
                    combined_response.append(f"💡 **매물 추천 결과**\n\n{recommendation_response}")
                
                elif task.task_type == TaskType.COMPARISON:
                    comparison_response = task.result.get("comparison_response", "")
                    comparison_data = task.result.get("comparison_data", {})
                    
                    # 비교 작업에서는 매물 데이터 설정하지 않고 텍스트 응답만 추가
                    # 단, 첫 번째 검색 결과가 아직 설정되지 않은 경우에만 설정
                    if not search_results_set and comparison_data.get("results"):
                        final_search_results = comparison_data
                        result_type = "search_result"
                        search_results_set = True
                    
                    # 비교 결과 섹션 헤더 추가
                    combined_response.append(f"⚖️ **매물 비교 결과**\n\n{comparison_response}")
                
                elif task.task_type == TaskType.ANALYSIS:
                    analysis_response = task.result.get("analysis_response", "")
                    analyzed_data = task.result.get("analyzed_data", {})
                    
                    # 분석 작업에서는 매물 데이터 설정하지 않고 텍스트 응답만 추가
                    # 단, 첫 번째 검색 결과가 아직 설정되지 않은 경우에만 설정
                    if not search_results_set and analyzed_data.get("results"):
                        final_search_results = analyzed_data
                        result_type = "search_result"
                        search_results_set = True
                    
                    # 분석 결과 섹션 헤더 추가
                    combined_response.append(f"📊 **매물 분석 결과**\n\n{analysis_response}")
                
                elif task.task_type == TaskType.WISHLIST:
                    wishlist_response = task.result.get("response", "")
                    wishlist_search_results = task.result.get("search_results", {})
                    wishlist_data = task.result.get("wishlist_data", {})
                    
                    # 찜 목록 데이터도 첫 번째 검색 결과가 아직 설정되지 않은 경우에만 설정
                    if not search_results_set:
                        if wishlist_data and wishlist_data.get("results"):
                            final_search_results = wishlist_data
                            result_type = "search_result"
                            search_results_set = True
                        elif wishlist_search_results and wishlist_search_results.get("results"):
                            final_search_results = wishlist_search_results
                            result_type = "search_result"
                            search_results_set = True
                    
                    # 찜 목록 결과 섹션 헤더 추가
                    combined_response.append(f"❤️ **찜 목록**\n\n{wishlist_response}")
                
                elif task.task_type == TaskType.CHAT:
                    chat_response = task.result.get("response", "")
                    combined_response.append(chat_response)
            
            elif task.status == "failed":
                error_msg = f"⚠️ {task.task_type.value} 작업 중 오류가 발생했습니다: {task.error}"
                multi_agent_logger.error(error_msg)
                combined_response.append(error_msg)
        
        # 최종 응답 생성
        final_response = "\n\n".join(filter(None, combined_response))
        multi_agent_logger.info(f"최종 응답 생성: 길이={len(final_response)}, 타입={result_type}")
        
        if not final_response:
            final_response = "요청을 처리하지 못했습니다."
            multi_agent_logger.warning("⚠️ [응답 오류] 최종 응답이 비어있음")
        
        # 검색 결과 변환 및 PropertyItem 스키마 적용
        list_results = final_search_results.get("results", [])
        if list_results:
            # 결과를 PropertyItem 스키마에 맞게 정규화
            normalized_results = []
            for item in list_results:
                try:
                    # 기본 필드 정규화
                    normalized_item = {
                        "_id": str(item.get("_id", "")),
                        "gu": item.get("gu", ""),
                        "dong": item.get("dong", ""),
                        "jibun": item.get("jibun", ""),
                        "aptNm": item.get("aptNm", ""),
                        "floor": item.get("floor", ""),
                        "area_pyeong": item.get("area_pyeong", ""),
                        "deposit": item.get("deposit", ""),
                        "monthlyRent": item.get("monthlyRent", ""),
                        "rent_type": item.get("rent_type", ""),
                        "nearest_station": item.get("nearest_station", ""),
                        "distance_to_station": float(item.get("distance_to_station", 0)),
                        "score": float(item.get("score", 0)),
                        "lat": float(item.get("lat", 0)) if item.get("lat") else None,
                        "lng": float(item.get("lng", 0)) if item.get("lng") else None
                    }
                    normalized_results.append(normalized_item)
                except Exception as e:
                    multi_agent_logger.error(f"결과 정규화 오류: {e}, 원본 항목 사용")
                    normalized_results.append(item)
            
            # 렌트 타입 정보 추가 및 ObjectId 변환
            list_results = add_rent_type_info(normalized_results)
            # ObjectId를 문자열로 변환
            for result in list_results:
                if '_id' in result and hasattr(result['_id'], '__str__'):
                    result['_id'] = str(result['_id'])
        
        # 최종 결과 반환
        result = {
            "reply": final_response,
            "agents_used": agents_used + ["LANGCHAIN"],
            "search_results": final_search_results,
            "results": list_results,
            "type": result_type,
            "tasks_completed": len(completed_tasks),
            "langchain_enabled": True
        }
        
        # 메모리에 대화 저장 (성능을 위해 백그라운드로 처리)
        try:
            if user_query and final_response:
                # 메모리에 저장 (사용자 입력과 AI 응답)
                self.memory.save_context(
                    {"input": user_query},
                    {"output": final_response}
                )
                multi_agent_logger.info("대화 메모리 저장 완료")
                
                # 메모리 크기 체크 (다시 한번)
                self._manage_memory_size()
        except Exception as e:
            multi_agent_logger.error(f"메모리 저장 중 오류: {e}")
        
        return result


# 전역 오케스트레이터 인스턴스
enhanced_orchestrator = EnhancedMultiAgentOrchestrator()


# 메인 처리 함수
async def process_user_message_enhanced(user_query: str, user_id: Optional[int] = None) -> Dict[str, Any]:
    """향상된 다중 에이전트로 사용자 메시지 처리"""
    return await enhanced_orchestrator.process_user_message(user_query, user_id)


# WebSocket 핸들러
async def enhanced_websocket_chat_handler(ws):
    """향상된 WebSocket 다중 에이전트 채팅 처리"""
    from starlette.websockets import WebSocketDisconnect
    
    await ws.accept()
    multi_agent_logger.info("Enhanced Multi-Agent WebSocket 연결 성공")
    
    try:
        while True:
            try:
                # 메시지 수신
                msg = await ws.receive_json()
                user_text = msg.get("content", "")
                user_id = msg.get("user_id", None)
                
                multi_agent_logger.info(f"수신된 메시지: {msg}")
                multi_agent_logger.info(f"사용자 ID: {user_id}")
                
                if not user_text.strip():
                    continue
                
                multi_agent_logger.info(f"사용자 (ID: {user_id}): {user_text}")
                
                # 향상된 다중 에이전트로 처리
                result = await process_user_message_enhanced(user_text, user_id)
                
                multi_agent_logger.info(f"{'/'.join(result['agents_used'])} Agents: {result['reply'][:100]}...")
                
                # 응답 전송
                response_data = {
                    "reply": result["reply"],
                    "type": result["type"],
                    "agents_used": result.get("agents_used", []),
                    "results": result.get("results", []),
                    "tasks_completed": result.get("tasks_completed", 0)
                }
                
                await ws.send_json(response_data)
                
            except WebSocketDisconnect:
                multi_agent_logger.info("클라이언트 연결 끊김 (정상)")
                break
            except Exception as e:
                multi_agent_logger.error(f"메시지 처리 오류: {e}")
                try:
                    await ws.send_json({
                        "reply": "서비스 처리 중 오류가 발생했습니다.",
                        "type": "error",
                        "agents_used": ["ERROR"],
                        "results": []
                    })
                except Exception as send_error:
                    multi_agent_logger.error(f"오류 메시지 전송 실패: {send_error}")
                    break
    
    except WebSocketDisconnect:
        multi_agent_logger.info("WebSocket 연결 해제됨")
    except Exception as e:
        multi_agent_logger.error(f"Enhanced WebSocket 핸들러 오류: {e}")
    finally:
        multi_agent_logger.info("Enhanced WebSocket 연결 정리 완료")
