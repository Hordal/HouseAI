#OpenAI를 이용한 실거래가 데이터 임베딩 및 MongoDB에 저장하기

1. .env 파일에 MongoDB와 OpenAI API 링크 저장
[예시]
OPENAI_API_KEY=sk-proj-...
MONGO_URI=mongodb+srv://...
SERVICE_KEY= "국토교통부 아파트 전월세 실거래가 API KEY"

2. fetch_rent_data.py 실행

python fetch_rent_data.py
