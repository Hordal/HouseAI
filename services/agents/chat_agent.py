"""
Chat Agent for Multi-Agent Chat Service
일반 대화 처리 에이전트
"""

import os
from typing import Dict, List, Any

# Claude API 클라이언트 생성
try:
    import anthropic
    claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    USE_CLAUDE = True
    print("✅ Claude client initialized successfully")
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY not found, falling back to OpenAI")
        USE_CLAUDE = False
except ImportError as e:
    print(f"❌ Anthropic package not installed: {e}")
    print("💡 To enable Claude: pip install anthropic")
    USE_CLAUDE = False
except Exception as e:
    print(f"❌ Claude client initialization failed: {e}")
    USE_CLAUDE = False

# OpenAI 클라이언트 생성 (폴백용)
if not USE_CLAUDE or not os.getenv("ANTHROPIC_API_KEY"):
    try:
        from openai import OpenAI
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        if not openai_client.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        print("✅ OpenAI client initialized as fallback")
    except Exception as e:
        print(f"❌ OpenAI client initialization failed: {e}")
        raise


class ChatAgent:
    """일반 대화 처리 에이전트"""
    
    def __init__(self):
        self.system_prompt = """
        너는 집톡AI의 친근한 대화 Agent야.
        집톡AI 서비스는 부동산 매물 검색과 관련된 다양한 질문에 답변하는 서비스야.
        너의 주요 역할은 사용자와 자연스럽게 대화하는 거야.

        역할:
        - 인사 및 일반적인 대화 처리
        - 서비스 소개 및 도움말 제공
        - 사용자와의 자연스러운 상호작용
        - 집톡AI 서비스에 대한 안내 
        - 이외의 질문에는 답변을 제공하지 않는다고 명시
        응답 스타일:
        - 친근하고 도움이 되는 톤
        - 사용자 질문에 대한 명확한 답변
        - 대화가 길어지면 요약 제공
        """
    
    def chat_response(self, user_query: str, history: list = None) -> str:
        """이전 대화 기록을 요약해 포함한 일반 대화 응답 생성"""
        try:
            if USE_CLAUDE and os.getenv("ANTHROPIC_API_KEY"):
                print("🤖 Using Claude for chat response")
                return self._chat_with_claude(user_query, history)
            else:
                print("🤖 Using OpenAI for chat response")
                return self._chat_with_openai(user_query, history)
        except Exception as e:
            print(f"❌ Chat Agent 오류: {e}")
            return "안녕하세요! HouseAI입니다. 부동산 매물 검색을 도와드릴 수 있습니다."
    
    def _chat_with_claude(self, user_query: str, history: list = None) -> str:
        """Claude를 사용한 대화 응답 생성"""
        try:
            # Claude용 메시지 구성
            messages = []
            MAX_HISTORY = 3
            SUMMARY_TRIGGER = 10
            
            if history and len(history) > SUMMARY_TRIGGER:
                # 앞부분 요약 생성
                summary_text = "이전 대화 요약: "
                for h in history[:-MAX_HISTORY]:
                    if h["role"] == "user":
                        summary_text += f"[사용자] {h['content']} "
                    elif h["role"] == "assistant":
                        summary_text += f"[AI] {h['content']} "
                summary_text = summary_text[:500]
                messages.append({"role": "assistant", "content": summary_text})
                # 최근 대화만 추가
                messages.extend(history[-MAX_HISTORY:])
            elif history:
                messages.extend(history[-MAX_HISTORY:])
            
            messages.append({"role": "user", "content": user_query})
            
            response = claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                temperature=0.3,
                system=self.system_prompt,
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            print(f"Claude API 오류: {e}")
            # OpenAI로 폴백
            return self._chat_with_openai(user_query, history)
    
    def _chat_with_openai(self, user_query: str, history: list = None) -> str:
        """OpenAI를 사용한 대화 응답 생성"""
        try:
            messages = [{"role": "system", "content": self.system_prompt}]
            MAX_HISTORY = 3
            SUMMARY_TRIGGER = 10
            
            if history and len(history) > SUMMARY_TRIGGER:
                # 앞부분 요약 생성
                summary_text = "이전 대화 요약: "
                for h in history[:-MAX_HISTORY]:
                    if h["role"] == "user":
                        summary_text += f"[사용자] {h['content']} "
                    elif h["role"] == "assistant":
                        summary_text += f"[AI] {h['content']} "
                summary_text = summary_text[:500]
                messages.append({"role": "assistant", "content": summary_text})
                # 최근 대화만 추가
                messages.extend(history[-MAX_HISTORY:])
            elif history:
                messages.extend(history[-MAX_HISTORY:])
            
            messages.append({"role": "user", "content": user_query})
            
            response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI API 오류: {e}")
            return "안녕하세요! HouseAI입니다. 부동산 매물 검색을 도와드릴 수 있습니다."
