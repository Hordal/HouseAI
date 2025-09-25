# 부동산 AI 서비스

<img width="419" height="113" alt="123" src="https://github.com/user-attachments/assets/b0a91ebf-ff95-4698-8764-7f689515e745" />


## 💻 프로젝트 개요  
**"“부동산 탐색의 새로운 패러다임, 집톡TALK!”" <br/>**

**집Talk**는 부동산 서비스에 특화된 AI로, **국토 교통부 API**를 기반으로 하여 서초구의 부동산 탐색에 도움을 주는 프로젝트입니다. <br/>
현재 많은 플랫폼이 **복잡한 카테고리**, **주변시설 여부 확인** 등의 사용자가 많은 어려움를 겪고 있어, 이를 **LLM(대형 언어 모델)을 활용하여 대화형 AI**를 통해 쉽고 간편한 사용을 하기 위한 프로젝트입니다.    <br/>

**집톡**은 사용자의 needs에 맞춰, 사용자가 원하는 조건에 따른 검색, 매물에 따른 AI의 심층분석, 추천 등을 제공합니다.   <br/>
이를 위해 **RAG**와 **Langchain**을 사용하여 보다 정확하고 적절한 응답을 제공합니다.   <br/>

---

##  🔮 기대 효과

**1. 편리성 향상**<br/>
카테고리를 선택하지 않고 자연어를 통해 원하는 매물을 빠르게 찾을 수 있음.  <br/>
**2. 데이터 기반 매물 분석**<br/>
AI가 매물의 정보를 토대로 매물을 분석하여 부동산 선택에 도움을 줌.  <br/>
**3. 확장 가능성**<br/>
자연스러운 대화 개선<br/>
정해진 키워드 기반의 검색 시스템 → 프롬프트 엔지니어링 LLM이 수행할 수 있도록 변경<br/>



## 🧑‍🤝‍🧑 `멤버구성`

 - 팀장: 남상우
 - 문재성
 - 김연준
 - 이상원

<br/>

## ⚙️ `개발 환경`
![skills](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=JavaScript&logoColor=white)
![skills](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
<img src="https://img.shields.io/badge/MariaDB-003545?style=flat&logo=mariadb&logoColor=white">
![NodeJS](https://img.shields.io/badge/node.js-6DA55F?style=for-the-badge&logo=node.js&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-%234ea94b.svg?style=for-the-badge&logo=mongodb&logoColor=white)

![skills](https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)
![skills](https://img.shields.io/badge/GITHUB-E44C30?style=for-the-badge&logo=git&logoColor=white)
![skills](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![skills](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)

![skills](https://img.shields.io/badge/VSCode-0078D4?style=for-the-badge&logo=visual%20studio%20code&logoColor=white)
![skills](https://img.shields.io/badge/Miro-FFD02F?style=for-the-badge&logo=miro&logoColor=050038)
![skills](https://img.shields.io/badge/Canva-%2300C4CC.svg?&style=for-the-badge&logo=Canva&logoColor=white)
![skills](https://img.shields.io/badge/Notion-000000?style=for-the-badge&logo=notion&logoColor=white)

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![ChatGPT](https://img.shields.io/badge/chatGPT-74aa9c?style=for-the-badge&logo=openai&logoColor=white)
![ChatGPT](https://img.shields.io/badge/chatGPT-74aa9c?style=for-the-badge&logo=openai&logoColor=white)
<img src="https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white"> 

<br/>
<br/><h2>📂 패키지구조</h2>

  <summery><b>프론트엔드 패키지 구조</b></summery>
  <div markdown="1">
<details>
  <summary>코드</summary>
 
```
📦src
 ┣ 📂asset
 ┃ ┣ 📜ai.png
 ┃ ┣ 📜background.png
 ┃ ┣ 📜TALK.PNG
 ┃ ┗ 📜user.png
 ┣ 📂components
 ┃ ┣ 📜BusinessSection.css
 ┃ ┣ 📜BusinessSection.jsx
 ┃ ┣ 📜Chatbot.css
 ┃ ┣ 📜Chatbot.jsx
 ┃ ┣ 📜GuideSection.css
 ┃ ┣ 📜GuideSection.jsx
 ┃ ┣ 📜IntroSection.css
 ┃ ┣ 📜IntroSection.jsx
 ┃ ┣ 📜Map.jsx
 ┃ ┣ 📜Navbar.css
 ┃ ┣ 📜Navbar.jsx
 ┃ ┣ 📜Showlist.css
 ┃ ┣ 📜Showlist.jsx
 ┃ ┣ 📜StartSection.css
 ┃ ┗ 📜StartSection.jsx
 ┣ 📂constants
 ┣ 📂contexts
 ┣ 📂hooks
 ┣ 📂pages
 ┣ 📂services
 ┣ 📂stores
 ┣ 📂styles
 ┣ 📂types
 ┣ 📂utils
 ┣ 📜App.jsx
 ┗ 📜main.jsx

```
</details>


    
  </div>

   <summery><b>백엔드 패키지 구조</b><summery>
  <div markdown="1">

<details>
  <summary>코드</summary>
 
```
📦.
┣ 📜main.py
┣ 📜requirements.txt
┣ 📂config
┣ 📂core
┣ 📂db
┃ ┣ 📜__init__.py
┃ ┣ 📜database.py
┃ ┣ 📜list_database.py
┃ ┗ 📜user_database.py
┣ 📂middleware
┣ 📂public
┣ 📂read
┃ ┣ 📜MULTI_AGENT_GUIDE.md
┃ ┣ 📜react1.md
┃ ┣ 📜react2.md
┃ ┣ 📜UserDB.md
┃ ┗ 📂update_data
┃   ┣ 📜fetch_rent_data.md
┃   ┣ 📜fetch_rent_data.py
┃   ┣ 📜save_subway_data.py
┃   ┗ 📜subway_readme.md
┣ 📂routers
┃ ┣ 📜__init__.py
┃ ┣ 📜chat_router.py
┃ ┣ 📜list_router.py
┃ ┣ 📜user_router.py
┃ ┗ 📂v1
┣ 📂schemas
┃ ┣ 📜__init__.py
┃ ┣ 📜list_schemas.py
┃ ┣ 📜property.py
┃ ┗ 📜user.py
┣ 📂services
┃ ┣ 📜__init__.py
┃ ┣ 📜enhanced_multi_agent_service.py
┃ ┣ 📜list_services.py
┃ ┣ 📜user_service.py
┃ ┗ 📂agents
┃   ┣ 📜__init__.py
┃   ┣ 📜analysis_agent.py
┃   ┣ 📜chat_agent.py
┃   ┣ 📜comparison_agent.py
┃   ┣ 📜recommendation_agent.py
┃   ┣ 📜search_agent.py
┃   ┣ 📜sim_search_agent.py
┃   ┣ 📜utils.py
┃   ┗ 📜wishlist_LAM.py
```
</details>
    
  </div>


## 🎬 `아키텍처`

![시스템_인프라 구성도](https://github.com/user-attachments/assets/14b0c3c5-c1e9-4250-8c3a-a26f3d283b5c)


<br/>
<br/><h2>📌 주요 기능</h2>

### 🔍 국토교통부API
 - https://www.data.go.kr/data/15126474/openapi.do

### 📚 RAG & VectorStore 성능 향상  
 - **국토교통부API 메타데이터 개선**
    - <img width="512" height="296" alt="메타데이터" src="https://github.com/user-attachments/assets/72185b18-1cbb-4ea4-9430-3aad4b6b9907" />

 - **MultiAgent사용**
    - 총6개의 Agent로 분리
      - SearchAgent (검색)
      - SimSearchAgent (유사 검색)
      - AnalysisAgent (분석)
      - ComparisonAgent (비교)
      - RecommandationAgent (추천)
      - ChatAgent (대화)

### 📝 Prompt Engineering  
 - **ComparisonAgent**
    - 비교 방식 : 서술형에서 구조화된 표 형식으로 변경
    - 정보 구조 : 표 → 요약 → 상세설명으로 다층 구조
 - **RecommandationAgent**
    - 추천 구조 : 조건별 추천 및 기준별 추천(2인 가구, 4인가구 등)
    - 표현 방식 : 유연하고 정보 중심적 제안
    - 이해도 및 설득력 : 설명 구체화
 - **AnalysisAgent**
    - 가독성 : 정보 정렬, 간격, 중복 제거로 향상
    - 정보전달 : 구체적·친절한 어조, 사용자 중심 설명 도입
 - **ChatAgent**
    - 행동 유도성 : 질문 요청 등 명확한 유도
    - 정보 구조화 : 기능, 기술 정보를 명확히 입력
    - hallucination 감소

### 📊 다양한 LLM 사용
 - **GPT 4.1**
    - 매물에 관한 심층분석 및 추천
 - **Claude Sonnet 3.5**
    - 사용자의 의도파악, 일반적인 대화

## 🎃 웹 스크린 구성 및 기능

| **Home** | 

<img width="745" height="356" alt="화면" src="https://github.com/user-attachments/assets/b27b3968-5f1d-4ceb-aec2-c6717cb2d91c" /> 

|  **Dashboard**  | 

<img width="1919" height="954" alt="메인" src="https://github.com/user-attachments/assets/ce337083-b3a5-4a30-960d-072c83b92795" />

| **Compare** |

<img width="1919" height="951" alt="비교" src="https://github.com/user-attachments/assets/e163a719-1ea9-4680-b867-cb793ac442d9" />

|  **Login/Signup** | 

<img width="598" height="799" alt="로그인" src="https://github.com/user-attachments/assets/5f9e493a-d91d-4ff1-a4c8-0822ac1448c0" />
<img width="596" height="793" alt="회원가입" src="https://github.com/user-attachments/assets/9eaee8bd-6d23-4e02-b195-475425974fbd" />
