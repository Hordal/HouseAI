# Claude 지원 설정 가이드

HouseAI는 이제 OpenAI GPT와 Anthropic Claude 모델을 모두 지원합니다.

## 📋 필요한 패키지 설치

```bash
pip install anthropic langchain-anthropic
```

## 🔑 API 키 설정

`.env` 파일에 다음을 추가하세요:

```env
# OpenAI API 키 (기본값/폴백용)
OPENAI_API_KEY=your_openai_api_key_here

# Anthropic Claude API 키 (우선 사용)
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

## 🤖 모델 선택 우선순위

1. **Claude가 우선**: `ANTHROPIC_API_KEY`가 설정되어 있으면 Claude를 사용
2. **OpenAI 폴백**: Claude가 없으면 OpenAI GPT를 사용
3. **자동 감지**: 시스템이 자동으로 사용 가능한 모델을 선택

## 🔧 지원되는 모델

### Claude 모델
- `claude-3-sonnet-20240229` (기본값)
- `claude-3-opus-20240229`
- `claude-3-haiku-20240307`

### OpenAI 모델
- `gpt-4` (기본값)
- `gpt-4-turbo`
- `gpt-3.5-turbo`

## 🚀 사용법

### 자동 모델 선택 (권장)
```python
llm = _create_llm(temperature=0.2, model="auto")
```

### 특정 모델 지정
```python
# Claude 사용
llm = _create_llm(temperature=0.2, model="claude-3-sonnet-20240229")

# OpenAI 사용
llm = _create_llm(temperature=0.2, model="gpt-4")
```

## 💡 장점

### Claude의 장점
- 더 긴 컨텍스트 윈도우
- 한국어 처리 성능 우수
- 비용 효율성
- 창의적 작업에 강함

### OpenAI GPT의 장점
- 안정적인 성능
- 광범위한 지식베이스
- 코드 생성에 강함
- 빠른 응답 속도

## ⚠️ 주의사항

1. **API 키 보안**: API 키를 코드에 직접 하드코딩하지 마세요
2. **비용 관리**: 두 서비스 모두 사용량에 따라 과금됩니다
3. **폴백 메커니즘**: Claude 오류 시 자동으로 OpenAI로 전환됩니다

## 🔍 문제 해결

### Claude가 작동하지 않는 경우
1. `anthropic` 패키지가 설치되어 있는지 확인
2. `ANTHROPIC_API_KEY`가 올바르게 설정되어 있는지 확인
3. API 키가 유효한지 확인
4. 로그에서 오류 메시지 확인

### 설치 확인
```python
try:
    import anthropic
    print("Anthropic 패키지 설치됨")
except ImportError:
    print("Anthropic 패키지 설치 필요")
```

## 📊 성능 비교

| 특성 | Claude 3 Sonnet | GPT-4 |
|------|----------------|-------|
| 컨텍스트 윈도우 | 200K 토큰 | 8K-32K 토큰 |
| 한국어 지원 | 우수 | 양호 |
| 응답 속도 | 보통 | 빠름 |
| 비용 | 저렴 | 비쌈 |
| 창의성 | 높음 | 높음 |

## 🔗 추가 리소스

- [Anthropic API 문서](https://docs.anthropic.com/)
- [LangChain Anthropic 가이드](https://python.langchain.com/docs/integrations/chat/anthropic)
- [OpenAI API 문서](https://platform.openai.com/docs)
