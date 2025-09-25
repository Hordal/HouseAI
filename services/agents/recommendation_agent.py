"""
Recommendation Agent for Multi-Agent Chat Service
매물 추천 전담 에이전트

- 추천 예시, 추천 프롬프트, 추천 처리 로직 포함
"""

import json
from typing import List, Dict, Any, Optional
from openai import OpenAI
import os
from services.agents import utils
import re

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

def format_property_text(properties):
    def format_money(val):
        try:
            val = int(float(val))
        except Exception:
            return str(val)
        if val >= 10000:
            return f"{val//10000}억{val%10000 if val%10000 else ''}만"
        elif val > 0:
            return f"{val}만"
        else:
            return "0"
    def get_station_type(dist):
        try:
            d = float(dist)
            if d <= 250:
                return "역세권"
            elif d <= 500:
                return "준역세권"
            else:
                return "비역세권"
        except Exception:
            return "정보없음"
    lines = []
    for idx, prop in enumerate(properties, 1):
        apt = prop.get('aptNm', '')
        area = prop.get('area_pyeong', '')
        deposit = format_money(prop.get('deposit', 0))
        monthly = format_money(prop.get('monthlyRent', 0))
        dist = prop.get('distance_to_station', None)
        dist_val = None
        try:
            dist_val = int(float(dist)) if dist is not None and dist != '' else None
        except Exception:
            dist_val = None
        station_type = get_station_type(dist)
        dist_str = f"{station_type} {dist_val}m" if dist_val is not None else f"{station_type}"
        rent_type = prop.get('rent_type', '')
        # 전세/월세 구분 및 정보 순서 맞추기
        if rent_type == '전세' or (monthly == '0' or monthly == 0):
            info = f"전세. 보증금 {deposit}, {area}평, {dist_str}"
        else:
            info = f"월세. 보증금 {deposit}, 월세 {monthly}, {area}평, {dist_str}"
        # 여기서 번호를 prop['rank']로 출력 (없으면 idx)
        number = prop.get('rank', idx)
        lines.append(f"{number}. {apt}({info})")
    return '\n'.join(lines)

def get_suitable_area_range(family_size: int):
    # 1인: 7~15, 2인: 12~20, 3인: 17~25, 4인: 22~30, 5인: 27~35, ...
    min_area = 7 + (family_size - 1) * 5
    max_area = 15 + (family_size - 1) * 5
    return (min_area, max_area)

def get_suitable_area_range_text(family_size: int) -> str:
    min_area, max_area = get_suitable_area_range(family_size)
    return f"{family_size}인 가구에게는 {min_area}~{max_area}평이 적당합니다."

def postprocess_recommendation_text(text, property_names):
    # 후처리 불필요: AI가 번호+매물명 조합으로만 언급하도록 프롬프트 강화
    return text

class RecommendationAgent:
    def __init__(self):
        self.system_prompt = """
너는 부동산 매물 추천 전문 Agent야.
- 조건에 맞는 매물 추천 및 추천 사유 설명을 수행한다.
- 매물의 데이터를 일괄적으로 검증하고, 필수 필드가 누락된 매물은 제외한다. (제외된 매물에 대한 안내는 출력하지 않는다)
- 사용자가 매물을 번호로 이야기한다면 리스트[번호-1]로 매물에 접근할 수 있다.
- 소비자가 요구하는 매물 정보, 선호 거래 유형, 예산 등 조건이 있으면 그에 맞춰 추천한다.
- 조건이 없으면 가치 평가가 높은 순으로 추천한다.
- 추천 매물은 3개를 넘지 않는다.
- 추천 결과는 **표, 리스트, 마크다운, 테이블, 열, 행, 구분선, |, --- 등은 절대 사용하지 말고**, 반드시 자연스러운 문장(텍스트)만으로 각 매물의 장단점과 추천 사유를 설명하라.
- 각 매물 설명은 반드시 줄바꿈(\\n)으로 구분하라. (한 매물의 설명이 끝나면 줄바꿈)
- 예시 답변처럼 문장만 출력하라.
- 사용자의 가족 수, 평수, 예산, 역세권, 직장인 등 다양한 조건을 종합적으로 고려해 추천해야 한다.
- 가족 수 조건이 있으면, 해당 인원수에 맞는 평수 기준(예: 2인=12~20평, 4인=22~30평, 6인=32~40평 등)을 반드시 반영해서 추천하라.
- 직장인 가족이면 출퇴근 편의(역세권, 지하철 거리 등)도 반드시 고려하라.
- 예산, 신축/구축, 옵션 등도 조건에 있으면 반드시 반영하라.
- 각 매물 설명에는 반드시 평수(24평), 월세(90만원), 보증금(4억), 역세권(230m) 등 주요 정보를 괄호와 숫자+단위로 명확히 표기하라.
- 단, 추천 설명(답변)에서는 역세권 구분(역세권/준역세권/비역세권)만 언급하고, 거리(m)는 언급하지 말 것.
- 답변에서 매물은 반드시 'N번 매물(매물명)' 형식으로만 언급하고, 매물명만 단독으로 언급하지 마라. 예: '2번 매물(서초더샵포레)는 ...'처럼 번호+매물명 조합으로만 설명하라.

추천 예시1)
사용자 요청: 전세 아파트에서 살고싶어. 역세권이면 좋겠어. 가격이 5억 이하의 매물을 추천해줘.
매물 데이터:
1. 서초역 아파트 (25평, 보증금 5억 5천, 월세 0, 역세권 100m)
2. 방배역 오피스텔 (15평, 보증금 2억, 월세 80, 역세권 300m)
3. 교대역 빌라 (18평, 보증금 4억 8천, 월세 0, 역세권 600m)
**답변 예시(텍스트)**
3번 매물(교대역 빌라)가 가장 추천할 만합니다. 예산 5억 이하에 부합하고, 전세 매물로서 가격 대비 평수가 적당합니다. 역세권 입지로 출퇴근이 편리합니다.
1번 매물(서초역 아파트)는 평수와 역세권 입지는 좋으나 예산을 초과합니다.
2번 매물(방배역 오피스텔)은 월세 매물로 조건에 부합하지 않습니다.

추천 예시2)
사용자 요청: 4인 가족 직장인에게 추천해줘
매물 데이터:
1. 임광 (28평, 보증금 4억, 월세 90, 지하철까지 180m)
2. 서초더샵포레 (24평, 보증금 5억, 월세 100, 지하철까지 300m)
3. 정광아파트 (18평, 보증금 1억, 월세 60, 지하철까지 800m)
**답변 예시(텍스트)**
1번 매물(임광)이 가장 추천할 만합니다. 28평의 넓은 공간과 역세권 입지로 출퇴근이 편리하며, 가족 모두가 쾌적하게 생활할 수 있습니다.
2번 매물(서초더샵포레)도 평수와 환경이 좋지만, 1번 매물에 비해 역과의 거리가 더 멉니다.
3번 매물(정광아파트)는 평수가 작아 4인 가족에게는 다소 비좁을 수 있습니다.
"""

    def recommend(self, properties: List[Dict[str, Any]], user_query: str, exclude_property: Optional[Dict[str, Any]] = None) -> str:
        """
        매물 추천 메인 메서드
        - 입력: properties (매물 리스트), user_query (사용자 요청), exclude_property (추천에서 제외할 기준 매물)
        - 출력: 추천 결과(문자열)
        """
        if properties is None:
            properties = []
        if not properties or not isinstance(properties, list):
            return "추천할 매물이 없습니다. (매물 데이터가 비어있거나 잘못됨)"
        try:
            # 가족 수(인원수) 추출
            family_size = None
            match = re.search(r'(\d+)\s*인[가|가구| 가족]', user_query)
            if match:
                family_size = int(match.group(1))
            # 평수 기준 텍스트
            area_range_text = ""
            filtered_properties = properties
            if family_size:
                area_range_text = get_suitable_area_range_text(family_size)
                min_area, max_area = get_suitable_area_range(family_size)
                # 평수 기준에 맞는 매물만 우선 추천
                filtered_properties = [
                    prop for prop in properties
                    if min_area <= float(prop.get('area_pyeong', 0)) <= max_area
                ]
                # 만약 기준에 맞는 매물이 없으면 전체에서 추천
                if not filtered_properties:
                    filtered_properties = properties
            simplified_properties = []
            exclude_id = None
            if exclude_property is not None:
                exclude_id = str(exclude_property.get("_id", ""))
            for idx, prop in enumerate(filtered_properties, 1):
                # 기준 매물과 동일한 매물은 추천 리스트에서 제외
                if exclude_id is not None and str(prop.get("_id", "")) == exclude_id:
                    continue
                simplified_prop = {
                    "aptNm": prop.get("aptNm", ""),
                    "rent_type": prop.get("rent_type", ""),
                    "deposit": prop.get("deposit", 0),
                    "monthlyRent": prop.get("monthlyRent", 0),
                    "area_pyeong": prop.get("area_pyeong", 0),
                    "distance_to_station": prop.get("distance_to_station", 0),
                    "rank": prop.get("rank", idx)
                }
                simplified_properties.append(simplified_prop)
            property_text = format_property_text(simplified_properties)
            response = openai_client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"""
                    사용자 요청: {user_query}
                    {area_range_text}
                    매물 데이터(각 매물 설명은 괄호와 숫자+단위로 표기, 줄바꿈(\\n)으로 구분):\n{property_text}

                    위 매물들 중에서 조건에 맞는 매물을 추천해주고, 추천 사유를 명확히 설명해줘.\n각 매물별 설명은 반드시 줄바꿈(\\n)으로 구분해서 출력해줘.
                    표, 리스트, 마크다운, 테이블, 열, 행, 구분선, |, --- 등은 절대 사용하지 말고, 반드시 자연스러운 문장(텍스트)만으로 답변해줘.
                    """}
                ],
                temperature=0.1
            )
            content = response.choices[0].message.content
            if not content or not isinstance(content, str):
                return "추천 결과를 생성하지 못했습니다."
            # 매물명 리스트 추출
            property_names = [prop.get('aptNm', '') for prop in simplified_properties if prop.get('aptNm', '')]
            content = postprocess_recommendation_text(content, property_names)
            return content
        except Exception as e:
            print(f"RecommendationAgent 오류: {e}")
            return "매물 추천 중 오류가 발생했습니다. (API 오류)"

def filter_properties_by_condition(properties, user_query):
    """
    사용자 쿼리의 간단한 키워드(전세/월세, 평수, 예산 등)로 매물 리스트를 필터링합니다.
    """
    if not properties or not isinstance(properties, list):
        return []
    filtered = []
    query = user_query.lower()
    for prop in properties:
        # 예시: 전세/월세 필터
        if "전세" in query and prop.get("rent_type") != "전세":
            continue
        if "월세" in query and prop.get("rent_type") != "월세":
            continue
        # 예시: 평수 필터
        if "평" in query:
            import re
            match = re.search(r'(\d+)\s*평', query)
            if match:
                try:
                    area = float(prop.get("area_pyeong", 0))
                    if area < float(match.group(1)):
                        continue
                except Exception:
                    pass
        # 예시: 예산(보증금) 필터
        if "억" in query or "만원" in query:
            import re
            match = re.search(r'(\d+)[억만]*\s*이하', query)
            if match:
                try:
                    deposit = float(prop.get("deposit", 0))
                    limit = float(match.group(1))
                    if "억" in query:
                        limit *= 10000
                    if deposit > limit:
                        continue
                except Exception:
                    pass
        filtered.append(prop)
    return filtered

def recommend_with_fallback(properties, user_query, search_func):
    # 1. 기존 결과에서 조건 필터링
    filtered = filter_properties_by_condition(properties, user_query)
    if filtered:
        agent = RecommendationAgent()
        return agent.recommend(filtered, user_query)
    else:
        # 2. 안내 메시지 + 재검색
        print("조건에 맞는 매물이 없습니다. 조건에 맞게 재검색을 진행합니다.")
        new_results = search_func(user_query)
        if new_results:
            agent = RecommendationAgent()
            return agent.recommend(new_results, user_query)
        else:
            return "조건에 맞는 매물이 없습니다."
