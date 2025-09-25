import React, { useEffect, useRef, useState, useMemo } from "react";
import "./IntroSection.css";
import userIcon from "../asset/user.png";
import aiIcon from "../asset/ai.png";

export default function IntroSection() {
  const texts = useMemo(() => [
    "나는 조용하고 교통이 편리한 집을 찾고 있어.",
    "해당하는 조건의 매물은 강남구 역삼동 원룸, 월세 80만원입니다.",
    "그럼 너가 추천하는 건 어디야?",
    "저는 강남구 역삼동에 있는 원룸을 추천해드리고 싶어요!"
  ], []);

  const [visibleTexts, setVisibleTexts] = useState(new Array(4).fill(false));
  const [typingTexts, setTypingTexts] = useState(new Array(4).fill(false));
  const textRefs = useRef([]);

  useEffect(() => {
    const showBubbleSequentially = (currentIndex) => {
      if (currentIndex >= texts.length) return;

      // 아바타 먼저 표시
      setVisibleTexts(prev => {
        const newState = [...prev];
        newState[currentIndex] = true;
        return newState;
      });

      // 아바타가 나타난 후 말풍선 표시 및 타이핑 애니메이션 시작
      setTimeout(() => {
        setTypingTexts(prev => {
          const newState = [...prev];
          newState[currentIndex] = true;
          return newState;
        });

        // 타이핑 애니메이션 완료 후 다음 말풍선 표시
        const typingDuration = 3000 + 500; // 3초 타이핑 + 0.5초 여유시간
        setTimeout(() => {
          showBubbleSequentially(currentIndex + 1);
        }, typingDuration);
      }, 800); // 아바타 나타나는 애니메이션 후 0.8초 대기
    };

    // 테스트용: 즉시 애니메이션 시작
    const timer = setTimeout(() => {
      showBubbleSequentially(0);
    }, 1000);

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            // 첫 번째 말풍선부터 순차적으로 표시
            clearTimeout(timer); // 자동 시작 타이머 클리어
            showBubbleSequentially(0);
          }
        });
      },
      { threshold: 0.3 }
    );

    // 첫 번째 요소만 관찰
    if (textRefs.current[0]) {
      observer.observe(textRefs.current[0]);
    }

    return () => {
      clearTimeout(timer);
      observer.disconnect();
    };
  }, [texts]);

  return (
    <div className="intro-section">
      <div className="intro-header">
        <h1 className="intro-title">
          <span className="title-accent">🏠</span>
          집 Talk 소개
          <span className="title-accent">💬</span>
        </h1>
        <div className="intro-subtitle">
          당신만을 위한 AI 부동산 컨시어지
        </div>
        <p className="intro-desc">
          <span className="highlight-text">AI 기반 부동산 추천 웹 서비스</span> 
          <strong className="brand-name">"집 Talk"</strong>은 
          사용자와 <span className="ai-text">Chat AI</span>의 자연스러운 대화를 통해 
          <span className="feature-text">맞춤형 매물을 찾아드리는</span> 혁신적인 서비스입니다.
        </p>
        <div className="intro-features">
          <div className="feature-item">
            <span className="feature-icon">🤖</span>
            <span>AI 맞춤 추천</span>
          </div>
          <div className="feature-item">
            <span className="feature-icon">💭</span>
            <span>자연스러운 대화</span>
          </div>
          <div className="feature-item">
            <span className="feature-icon">🎯</span>
            <span>정확한 매물 검색</span>
          </div>
        </div>
      </div>
      
      <div className="animation-container">
        {texts.map((text, index) => (
          <div
            key={index}
            ref={(el) => textRefs.current[index] = el}
            className={`animated-text ${index % 2 === 0 ? 'left' : 'right'} ${visibleTexts[index] ? 'visible' : ''}`}
          >
            <div className="chat-container">
              {index % 2 === 0 ? (
                <>
                  <div className={`avatar-container left ${visibleTexts[index] ? 'visible' : ''}`}>
                    <img src={userIcon} alt="User" className="avatar" />
                  </div>
                  <div className={`chat-bubble ${typingTexts[index] ? 'visible' : ''}`}>
                    <span className={`typing-text ${typingTexts[index] ? 'typing' : ''}`}>
                      {text}
                    </span>
                  </div>
                </>
              ) : (
                <>
                  <div className={`chat-bubble ${typingTexts[index] ? 'visible' : ''}`}>
                    <span className={`typing-text ${typingTexts[index] ? 'typing' : ''}`}>
                      {text}
                    </span>
                  </div>
                  <div className={`avatar-container right ${visibleTexts[index] ? 'visible' : ''}`}>
                    <img src={aiIcon} alt="AI" className="avatar" />
                  </div>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
      
      <hr className="intro-divider" />
    </div>
  );
}
