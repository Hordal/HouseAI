"""
Comparison Agent for Multi-Agent Chat Service
매물 비교 전담 에이전트

- 비교 예시, 비교 프롬프트, 비교 처리 로직 포함
"""

import json
from typing import List, Dict, Any
from openai import OpenAI
import os
from services.agents.utils import get_average_property

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

class ComparisonAgent:
    def __init__(self):
        self.system_prompt = """
- 너는 부동산 매물 비교 전문 Agent야.
- 매물 데이터는 리스트 형태로 제공되며, 각 매물은 딕셔너리 형태로 되어 있어.
- 매물을 번호는 리스트 index+1 (1부터 시작)으로 표기한다.
- 너는 항상 답변만을 제공하며 사용자의 요청과 매물 데이터, 평균 데이터는 답변에 제공하지 않는다.
- 표는 가로로 너무 길게 나오지 않도록 주의하고, 텍스트로 결과를 출력한다.
- 표의 가로 최대 길이는 20자이하로 한다.
- 평균 데이터를 기준으로 매물 데이터의 가치를 판단하고, 

비교 예시1)
사용자 요청: 1번과 3번 매물을 비교해줘.
매물 데이터:
[
  {"aptNm": "서초역 아파트", "rent_type": "전세", "deposit": 50000, "monthlyRent": 0, "area_pyeong": 84, "distance_to_station": 180, "price_per_py": 595.24, "price_value": 141.13},
  {"aptNm": "교대역 빌라", "rent_type": "전세", "deposit": 47000, "monthlyRent": 0, "area_pyeong": 75, "distance_to_station": 600, "price_per_py": 626.67, "price_value": 119.76}
]
평균 데이터:
{"aptNm": "평균 매물", "rent_type": "N/A", "deposit": 48500.0, "monthlyRent": 0.0, "area_pyeong": 79.5, "distance_to_station": 390.0, "price_per_py": 610.96, "price_value": 130.45}

**답변 예시(텍스트)**
서초역 아파트는 넓은 평수와 역세권이라는 장점이 있으며, 가격이 다소 높다는 단점이 있습니다. 교대역 빌라는 예산에 부합하고 적당한 평수이지만, 비역세권이라는 점이 아쉽습니다.
---

비교 예시2)
사용자 요청: 5번부터 9번까지의 매물들 중에 뭐가 나아?
매물 데이터:
[
  {"aptNm": "강남역 오피스텔", "rent_type": "월세", "deposit": 20000, "monthlyRent": 80, "area_pyeong": 25, "distance_to_station": 100, "price_per_py": 800.0, "price_value": 31.25},
  {"aptNm": "역삼역 아파트", "rent_type": "월세", "deposit": 30000, "monthlyRent": 60, "area_pyeong": 30, "distance_to_station": 350, "price_per_py": 1000.0, "price_value": 30.0},
  {"aptNm": "삼성동 아파트", "rent_type": "월세", "deposit": 25000, "monthlyRent": 70, "area_pyeong": 28, "distance_to_station": 200, "price_per_py": 892.86, "price_value": 31.36},
  {"aptNm": "논현동 빌라", "rent_type": "월세", "deposit": 22000, "monthlyRent": 75, "area_pyeong": 26, "distance_to_station": 180, "price_per_py": 846.15, "price_value": 30.74},
  {"aptNm": "신사동 오피스텔", "rent_type": "월세", "deposit": 27000, "monthlyRent": 65, "area_pyeong": 29, "distance_to_station": 250, "price_per_py": 931.03, "price_value": 31.15}
]
평균 데이터:
{"aptNm": "평균 매물", "rent_type": "N/A", "deposit": 24800.0, "monthlyRent": 70.0, "area_pyeong": 27.6, "distance_to_station": 216.0, "price_per_py": 894.41, "price_value": 30.9}

**답변 예시(표)**
5. 강남역 오피스텔
6. 역삼역 아파트
7. 삼성동 아파트
8. 논현동 빌라
9. 신사동 오피스텔

|       매물명       |면적(평)| 역 거리 | 평당가 | 가격가치 |
| ------------------| ----- | ------ | ----- | ------ |
|   강남역 오피스텔   |  25   |  100   | 800   | 31.25  |
|   역삼역 아파트    |   30   |  350  |  1000  | 30.0   |
|   삼성동 아파트    |  28    |  200  | 892.86 | 31.36 |
|   논현동 빌라      |  26   |  180   | 846.15 | 30.74 |
|   신사동 오피스텔  |  29    |  250  | 931.03 | 31.15 |

평균 매물은 전체 매물의 평균값을 기준으로 작성되었으며, 
각 매물의 특징을 종합적으로 고려하여 작성되었습니다.
- 강남역 오피스텔은 역세권에 위치하고 있어 교통이 편리하며, 가격 대비 평당가가 높습니다.
- 역삼역 아파트는 평당가가 가장 높지만, 역과의 거리가 다소 멀어 교통이 불편할 수 있습니다.
- 삼성동 아파트는 가격과 평당가가 적절히 균형을 이루고 있으며, 역과의 거리도 적당합니다.
- 논현동 빌라는 가격이 저렴하고 평당가도 적당하지만, 역과의 거리가 다소 멀어 교통이 불편할 수 있습니다.
- 신사동 오피스텔은 평당가가 높고, 역과의 거리가 적당하여 교통이 편리합니다.

---

비교 예시3)
사용자 요청: 5,6,8번 매물들 중에 뭐가 제일 좋아?
매물 데이터:
[
  {"aptNm": "삼성동 아파트", "rent_type": "월세", "deposit": 25000, "monthlyRent": 70, "area_pyeong": 28, "distance_to_station": 200, "price_per_py": 892.86, "price_value": 31.36},
  {"aptNm": "논현동 빌라", "rent_type": "월세", "deposit": 22000, "monthlyRent": 75, "area_pyeong": 26, "distance_to_station": 180, "price_per_py": 846.15, "price_value": 30.74},
  {"aptNm": "신사동 오피스텔", "rent_type": "월세", "deposit": 27000, "monthlyRent": 65, "area_pyeong": 29, "distance_to_station": 250, "price_per_py": 931.03, "price_value": 31.15}
]
평균 데이터:
{"aptNm": "평균 매물", "rent_type": "N/A", "deposit": 24666.67, "monthlyRent": 70.0, "area_pyeong": 27.67, "distance_to_station": 210.0, "price_per_py": 890.01, "price_value": 31.08}

**답변 예시(표)**
5. 삼성동 아파트
6. 논현동 빌라
8. 신사동 오피스텔
"""

    def compare(self, properties: List[Dict[str, Any]], user_query: str) -> str:
        if not properties or not isinstance(properties, list) or len(properties) < 2:
            return "비교할 매물이 2개 이상 필요합니다. (매물 데이터가 비어있거나 잘못됨)"
        try:
            simplified_properties = []
            for prop in properties:
                simplified_prop = {
                    "aptNm": prop.get("aptNm", ""),
                    "rent_type": prop.get("rent_type", ""),
                    "deposit": prop.get("deposit", 0),
                    "monthlyRent": prop.get("monthlyRent", 0),
                    "area_pyeong": prop.get("area_pyeong", 0),
                    "distance_to_station": prop.get("distance_to_station", 0),
                    "price_per_py": prop.get("price_per_py", 0),
                    "price_value": prop.get("price_value", 0)
                }
                simplified_properties.append(simplified_prop)
            # 평균값 추가
            avg_prop = get_average_property(properties)
            response = openai_client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"""
                    사용자 요청: {user_query}
                    매물 데이터: {json.dumps(simplified_properties, ensure_ascii=False)}
                    평균 매물 데이터: {json.dumps(avg_prop, ensure_ascii=False)}
                    """}
                ],
                temperature=0.1
            )
            content = response.choices[0].message.content
            if not content or not isinstance(content, str):
                return "비교 결과를 생성하지 못했습니다."
            return content
        except Exception as e:
            print(f"ComparisonAgent 오류: {e}")
            return "매물 비교 중 오류가 발생했습니다. (API 오류)"

