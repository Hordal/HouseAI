import json
from typing import List, Dict, Any
from openai import OpenAI
import os
from services.agents import utils
import re

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)



class AnalysisAgent:
    def __init__(self):
        self.system_prompt = """
너는 부동산 매물 분석 전문 Agent야.
- 매물 데이터(평수, 위치, 가격 등)를 기반으로 장점, 단점, 특이사항을 자연스러운 문장으로 요약한다.
- 사용자가 'N번 매물'을 지정하면 해당 매물만 분석하고, 없으면 전체를 분석한다.
- 최종 추천이나 선택은 절대 하지 않는다.
- 분석 결과는 반드시 "매물 이름([rank]번 매물): " 형식으로 시작해야 한다.
- 각 매물 분석이 끝나면 반드시 줄바꿈(\\n)을 두 번 넣어야 한다.
- 결과는 표, 리스트, 마크다운 없이 오직 텍스트 문장으로만 설명한다.
- **전세 매물의 경우, 월세(monthlyRent)가 0이거나 없더라도 특이사항이나 단점에 언급하지 않는다. 월세 매물의 경우에만 monthlyRent 정보를 분석에 반영한다.**

예시 답변)
신반포19(1번 매물): 32.37평의 넉넉한 공간과 역세권 입지로 출퇴근이 매우 편리합니다.\n보증금이 7억 5000만으로 합리적이며, 5인 가족이 쾌적하게 생활할 수 있습니다.\n단점으로는 주변 편의시설이 다소 부족할 수 있습니다.\n특이사항으로는 최근 리모델링이 완료되어 내부 상태가 우수합니다.\n"

분석 예시)
사용자 요청: 각 매물의 장단점과 특이사항을 분석해줘.
매물 데이터:
[
  {"aptNm": "서초역 아파트", "rent_type": "전세", "deposit": 50000, "monthlyRent": 0, "area_pyeong": 84, "distance_to_station": 180},
  {"aptNm": "교대역 빌라", "rent_type": "전세", "deposit": 47000, "monthlyRent": 0, "area_pyeong": 75, "distance_to_station": 600}
]
**답변 예시(텍스트)**
서초역 아파트(1번 매물): 넓은 평수와 역세권이라는 장점이 있으며, 가격이 다소 높다는 단점이 있습니다. 교대역 빌라(2번 매물): 예산에 부합하고 적당한 평수이지만, 비역세권이라는 점이 아쉽습니다.

분석 예시)
사용자 요청: 1번과 2번 매물의 장점, 단점, 특이사항을 알려줘.
매물 데이터:
[
  {"aptNm": "신촌역 오피스텔", "rent_type": "월세", "deposit": 10000, "monthlyRent": 70, "area_pyeong": 18, "distance_to_station": 50},
  {"aptNm": "이대역 아파트", "rent_type": "월세", "deposit": 15000, "monthlyRent": 60, "area_pyeong": 22, "distance_to_station": 400}
]
**답변 예시(텍스트)**
신촌역 오피스텔(2번 매물): 역과 매우 가까워 출퇴근이 편리하다는 장점이 있습니다. 다만, 면적이 좁고 월세가 다소 높다는 단점이 있습니다. 이대역 아파트(1번 매물): 면적이 더 넓고 월세가 저렴한 편이지만, 역과의 거리가 다소 먼 점이 아쉽습니다.
"""

    def analyze(self, properties: List[Dict[str, Any]], user_query: str) -> str:
        if not properties or not isinstance(properties, list):
            return "분석할 매물이 없습니다. (매물 데이터가 비어있거나 잘못됨)"
        try:
            simplified_properties = []
            for idx, prop in enumerate(properties, 1):
                price_per_py = utils.calculate_price_per_py({
                    "deposit": prop.get("deposit", 0),
                    "area_pyeong": prop.get("area_pyeong", 0)
                })
                price_value = utils.calculate_price_value(prop)
                simplified_prop = {
                    "aptNm": prop.get("aptNm", ""),
                    "rent_type": prop.get("rent_type", ""),
                    "deposit": prop.get("deposit", 0),
                    "monthlyRent": prop.get("monthlyRent", 0),
                    "area_pyeong": prop.get("area_pyeong", 0),
                    "distance_to_station": prop.get("distance_to_station", 0),
                    "price_per_py": price_per_py if price_per_py is not None else 0,
                    "price_value": price_value,
                    "rank": prop.get("rank", idx)
                }
                simplified_properties.append(simplified_prop)

            # 매물 번호를 명시적으로 포함하는 프롬프트 생성
            analysis_prompt = f"""
사용자 요청: {user_query}
매물 데이터: {json.dumps(simplified_properties, ensure_ascii=False)}

각 매물의 장점, 단점, 특이사항을 분석해줘. 
반드시 "매물 이름([rank]번 매물): " 형식으로 시작하고, 매물 분석이 끝나면 줄바꿈(\\n)을 두 번 넣어줘.
"""

            response = openai_client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.1
            )
            content = response.choices[0].message.content
            if not content or not isinstance(content, str):
                return "분석 결과를 생성하지 못했습니다."
            
            # 줄바꿈이 제대로 들어가도록 보정
            content = content.replace("\\n", "\n")
            return content
        except Exception as e:
            print(f"AnalysisAgent 오류: {e}")
            return "매물 분석 중 오류가 발생했습니다. (API 오류)"

    def handle_analysis_request(self, user_query: str, properties: list) -> str:
        """
        사용자 입력에서 N번 매물 지정 시 해당 매물만 분석, 없으면 전체 분석
        """
        match = re.search(r'(\d+)번', user_query)
        if match:
            idx = int(match.group(1)) - 1
            if 0 <= idx < len(properties):
                target = [properties[idx]]
                return self.analyze(target, user_query)
            else:
                return "해당 번호의 매물이 없습니다."
        else:
            return self.analyze(properties, user_query)
