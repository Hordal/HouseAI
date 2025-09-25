import { useState, useRef, useEffect, useCallback } from 'react';
import { getCurrentUser } from '../services/auth';
import './Chatbot.css';

export default function Chatbot({ updateProperties, onWishlistUpdate, fullHeight = false }) {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([]);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [isOpen, setIsOpen] = useState(fullHeight ? true : true);
  const [isConnected, setIsConnected] = useState(false);
  // 크기 상태 및 최대치(1.1배)
  const [width, setWidth] = useState(380);
  const [height, setHeight] = useState(500);
  const MAX_WIDTH = 660; // 600 * 1.1
  const MAX_HEIGHT = 880; // 800 * 1.1
  const [isResizing, setIsResizing] = useState(false);
  const resizeStart = useRef({ x: 0, y: 0, width: 0, height: 0 });

  const messagesEndRef = useRef(null);
  const scrollContainerRef = useRef(null);
  const wsRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleScroll = (e) => {
    const container = e.target;
    const isAtBottom = container.scrollTop >= container.scrollHeight - container.clientHeight - 50;
    setShowScrollButton(!isAtBottom);
  };

  // WebSocket 연결 설정
  const connectWebSocket = useCallback(() => {
    try {
      console.log('WebSocket 연결 시도 중...');
      const ws = new WebSocket('ws://localhost:8000/ws/chat');
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('✅ WebSocket 연결 성공');
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        console.log('📨 백엔드로부터 메시지 수신:', event.data);
        try {
          const data = JSON.parse(event.data);
          const botMessage = {
            text: data.reply || data.message || data.response || event.data,
            timestamp: new Date().toLocaleTimeString(),
            isBot: true
          };
          setMessages(prev => {
            // 로딩 메시지 제거하고 실제 응답 추가
            const filtered = prev.filter(msg => !msg.isLoading);
            return [...filtered, botMessage];
          });

          // 찜 작업 성공 감지 (results가 없어도 찜 목록 새로고침 필요)
          if (onWishlistUpdate && data.reply && (
            data.reply.includes('✅') && (
              data.reply.includes('찜 목록에서 삭제') ||
              data.reply.includes('찜 목록에 추가') ||
              data.reply.includes('번 매물을 찜') ||
              data.reply.includes('번 매물 삭제') ||
              data.reply.includes('번 매물 추가')
            )
          )) {
            console.log('💕 찜 작업 성공 감지 - 찜 목록 새로고침');
            onWishlistUpdate();
          }

          // 검색 결과가 있는 경우 Context에 저장
          if ((data.type === 'search_result' || data.type === 'analysis_result') && data.results && data.results.length > 0) {
            console.log('🏠 매물 결과 수신 (타입:', data.type, '):', data.results.length, '개');
            console.log('🏠 첫 번째 매물 샘플:', data.results[0]);
            
            // 찜 관련 응답인지 확인 (찜 관련 응답일 때는 매물 목록 업데이트 안함)
            const isWishlistRelated = data.reply && (
              data.reply.includes('찜 목록에서 삭제') ||
              data.reply.includes('찜 목록에 추가') ||
              data.reply.includes('찜 삭제') ||
              data.reply.includes('찜 추가') ||
              data.reply.includes('번 매물을 찜') ||
              data.reply.includes('번 매물 삭제') ||
              data.reply.includes('번 매물 추가') ||
              data.type === 'wishlist_result'
            );
            
            if (!isWishlistRelated) {
              // 위도/경도 정보 확인
              const propertiesWithCoords = data.results.filter(r => r.lat && r.lng);
              console.log('🗺️ 좌표 정보가 있는 매물:', propertiesWithCoords.length, '개');
              
              if (propertiesWithCoords.length > 0) {
                console.log('🗺️ 첫 번째 좌표 샘플:', {
                  aptNm: propertiesWithCoords[0].aptNm,
                  lat: propertiesWithCoords[0].lat,
                  lng: propertiesWithCoords[0].lng
                });
              }
              
              updateProperties(data.results);
            } else {
              console.log('🔕 찜 관련 응답으로 인해 매물 목록 업데이트 스킵');
              
              // 찜 작업이 성공한 경우 찜 목록 새로고침
              if (onWishlistUpdate && data.reply && (
                data.reply.includes('✅') || 
                data.reply.includes('성공') ||
                data.reply.includes('추가했습니다') ||
                data.reply.includes('삭제했습니다')
              )) {
                console.log('💕 찜 작업 성공으로 찜 목록 새로고침 요청');
                onWishlistUpdate();
              }
            }
          }
        } catch (error) {
          console.error('메시지 파싱 오류:', error);
          const botMessage = {
            text: event.data,
            timestamp: new Date().toLocaleTimeString(),
            isBot: true
          };
          setMessages(prev => {
            // 로딩 메시지 제거하고 실제 응답 추가
            const filtered = prev.filter(msg => !msg.isLoading);
            return [...filtered, botMessage];
          });
        }
      };

      ws.onclose = (event) => {
        console.log('❌ WebSocket 연결 종료:', event.code, event.reason);
        setIsConnected(false);
      };

      ws.onerror = (error) => {
        console.error('🚨 WebSocket 오류:', error);
        setIsConnected(false);
      };
    } catch (error) {
      console.error('🚨 WebSocket 연결 실패:', error);
    }
  }, [updateProperties, onWishlistUpdate]);

  // WebSocket 연결 해제
  const disconnectWebSocket = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
      setIsConnected(false);
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // WebSocket 연결 관리
  useEffect(() => {
    if (isOpen) {
      connectWebSocket();
    } else {
      disconnectWebSocket();
    }

    // 컴포넌트 언마운트 시 연결 해제
    return () => {
      disconnectWebSocket();
    };
  }, [isOpen, connectWebSocket]); // connectWebSocket 의존성 추가

  // 토글 버튼으로 채팅을 열 때 최신 메시지로 스크롤
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => {
        scrollToBottom();
      }, 100); // 렌더링 완료 후 스크롤
    }
  }, [isOpen]);

  const handleSend = () => {
    if (input.trim() && wsRef.current && isConnected) {
      // 사용자 메시지를 먼저 화면에 표시
      const userMessage = {
        text: input,
        timestamp: new Date().toLocaleTimeString(),
        isBot: false
      };

      // 로딩 메시지 추가
      const loadingMessage = {
        text: '',
        timestamp: new Date().toLocaleTimeString(),
        isBot: true,
        isLoading: true
      };

      setMessages(prev => [...prev, userMessage, loadingMessage]);

      // 현재 로그인한 사용자 정보 가져오기
      const currentUser = getCurrentUser();
      const userId = currentUser?.userId || null;
      
      console.log('👤 현재 사용자 정보:', currentUser);
      console.log('🆔 추출된 사용자 ID:', userId);

      // WebSocket으로 메시지 전송 (user_id 포함)
      const messageData = {
        content: input,
        type: 'chat',
        user_id: userId
      };
      console.log('📤 백엔드로 메시지 전송:', messageData);
      wsRef.current.send(JSON.stringify(messageData));

      setInput('');
    } else if (!isConnected) {
      // 연결이 안된 경우 로컬에서만 처리
      const userMessage = {
        text: input,
        timestamp: new Date().toLocaleTimeString(),
        isBot: false
      };
      setMessages(prev => [...prev, userMessage]);
      
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleSend();
  };

  const handleToggle = () => {
    setIsOpen(!isOpen);
    if (!isOpen) {
      // 채팅창이 열릴 때 최신 메시지로 스크롤
      setTimeout(() => {
        scrollToBottom();
      }, 100);
    }
  };

  // 리사이즈 시작 (왼쪽 위)
  const handleResizeStart = (e) => {
    setIsResizing(true);
    resizeStart.current = {
      x: e.clientX,
      y: e.clientY,
      width,
      height
    };
    document.body.style.userSelect = 'none';
  };

  // 리사이즈 중 (왼쪽 위)
  const handleResize = useCallback((e) => {
    if (!isResizing) return;
    const dx = e.clientX - resizeStart.current.x;
    const dy = e.clientY - resizeStart.current.y;
    setWidth(Math.max(280, Math.min(MAX_WIDTH, resizeStart.current.width - dx)));
    setHeight(Math.max(320, Math.min(MAX_HEIGHT, resizeStart.current.height - dy)));
  }, [isResizing]);

  // 리사이즈 끝
  const handleResizeEnd = () => {
    setIsResizing(false);
    document.body.style.userSelect = '';
  };

  useEffect(() => {
    if (isResizing) {
      window.addEventListener('mousemove', handleResize);
      window.addEventListener('mouseup', handleResizeEnd);
    } else {
      window.removeEventListener('mousemove', handleResize);
      window.removeEventListener('mouseup', handleResizeEnd);
    }
    return () => {
      window.removeEventListener('mousemove', handleResize);
      window.removeEventListener('mouseup', handleResizeEnd);
    };
  }, [isResizing, handleResize]);

  return (
    <>
      {/* ✅ 토글 버튼 - fullHeight가 아닐 때만 표시 */}
      {!fullHeight && (
        <button
          onClick={handleToggle}
          aria-label="채팅 열기/닫기"
          className="chatbot-toggle"
          style={{
            position: 'fixed',
            right: 24,
            bottom: 24,
            zIndex: 250,
            width: '9vw', // 기존 10vw에서 10% 줄임
            minWidth: 43, // 기존 48에서 10% 줄임
            maxWidth: 108, // 기존 120에서 10% 줄임
            height: '48px', // 기존 48px * 1.2 = 57.6px
            minHeight: 38, // 기존 32에서 1.2배
            maxHeight: 77 // 기존 64에서 1.2배
          }}
        >
          <div className="chatbot-toggle-bar" />
        </button>
      )}

      {/* ✅ 챗봇 UI - 열려 있을 때만 렌더링 */}
      {isOpen && (
        <div className="chatbot-container"
          style={{
            width: width,
            height: height,
            minWidth: 280,
            minHeight: 320,
            maxWidth: MAX_WIDTH,
            maxHeight: MAX_HEIGHT,
            // 기존 스타일은 Chatbot.css에서 유지
            position: 'fixed',
            right: 24,
            bottom: 72,
            zIndex: 200
          }}
        >
          {/* 리사이저 핸들 - 왼쪽 위 */}
          <div
            onMouseDown={handleResizeStart}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: 24,
              height: 24,
              cursor: "nwse-resize",
              background: "rgba(0,0,0,0.04)",
              zIndex: 10,
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "flex-start"
            }}
          >
            <svg width="18" height="18" viewBox="0 0 18 18" style={{opacity:0.5}}>
              <path d="M2 16L16 2M6 16L16 6M10 16L16 10" stroke="#888" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </div>

          {/* 메시지 출력 영역 */}
          <div 
            ref={scrollContainerRef}
            onScroll={handleScroll}
            className="chatbot-messages chatbot-scroll"
            style={{ flex: 1, minHeight: 0 }}
          >
            <div className="message-container-ai">
              <div className="message-bubble-ai">
                {fullHeight ? "어떤 것을 도와드릴까요?" : "원하는 집을 말씀해주세요!"}
                {!isConnected && (
                  <div style={{ fontSize: '12px', color: '#666', marginTop: '5px' }}>
                    (오프라인 모드)
                  </div>
                )}
              </div>
            </div>

            {messages.map((message, index) => (
              <div 
                key={index} 
                className={message.isBot ? "message-container-ai" : "message-container-user"}
              >
                <div className={message.isBot ? "message-bubble-ai" : "message-bubble-user"}>
                  {message.isLoading ? (
                    <div className="loading-message">
                      <div className="loading-spinner"></div>
                      <span>검색 중...</span>
                    </div>
                  ) : (
                    <div>{message.text}</div>
                  )}
                  <div className="message-timestamp">
                    {message.timestamp}
                  </div>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* 스크롤 다운 버튼 - 검색 프롬프트 바깥 중앙 위쪽 */}
          {showScrollButton && (
            <button
              onClick={scrollToBottom}
              className="scroll-down-button"
            >
              ↓
            </button>
          )}

          {/* 입력창 영역 - 항상 하단에 고정 */}
          <div className="chatbot-input-container" style={{ flexShrink: 0 }}>
            <input
              type="text"
              placeholder={isConnected ? "메시지를 입력하세요..." : "오프라인 모드 - 메시지 입력"}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              className="chatbot-input"
            />
            <button
              onClick={handleSend}
              className="chatbot-send-button"
              style={{
                backgroundColor: isConnected ? '#007bff' : '#6c757d'
              }}
            >
              전송
            </button>
          </div>
        </div>
      )}
    </>
  );
}
