import React, { useState, useEffect } from 'react';
import Navbar from '../components/Navbar';
import Showlist from '../components/Showlist';
import Chatbot from '../components/Chatbot';
import { getCurrentUserWishlist } from '../services/api';
import { isLoggedIn } from '../services/auth';
import './Compare.css';

export default function Compare() {
  const [properties, setProperties] = useState([]);
  const [selectedProperty, setSelectedProperty] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const updateProperties = (newProperties) => {
    setProperties(newProperties);
  };

  const selectProperty = (property) => {
    setSelectedProperty(property);
  };

  // 찜 작업 완료 후 찜 목록 새로고침을 위한 함수
  const handleWishlistUpdate = () => {
    fetchCurrentUserWishlist();
  };

  const handleLoginClick = () => {
    // 로그인 페이지를 팝업으로 열기
    const width = 600;
    const height = 800;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;
    
    const popup = window.open(
      '/login',
      'loginWindow',
      `width=${width},height=${height},left=${left},top=${top},scrollbars=yes,resizable=yes`
    );

    // 팝업에서 로그인 성공 메시지 수신 대기
    const handleMessage = (event) => {
      if (event.origin !== window.location.origin) return;
      
      if (event.data.type === 'LOGIN_SUCCESS') {
        // 로그인 성공 후 찜 목록 다시 불러오기
        fetchCurrentUserWishlist();
        
        // Navbar 컴포넌트가 업데이트되도록 커스텀 이벤트 발생
        window.dispatchEvent(new Event('userInfoChanged'));
        
        window.removeEventListener('message', handleMessage);
      }
    };

    window.addEventListener('message', handleMessage);
    
    // 팝업이 닫혔을 때 이벤트 리스너 제거
    const checkClosed = setInterval(() => {
      if (popup.closed) {
        clearInterval(checkClosed);
        window.removeEventListener('message', handleMessage);
      }
    }, 1000);
  };

  const fetchCurrentUserWishlist = async () => {
    try {
      // 로그인 상태 확인
      if (!isLoggedIn()) {
        setError('로그인이 필요합니다.');
        setLoading(false);
        return;
      }

      setLoading(true);
      const result = await getCurrentUserWishlist();
      
      if (result.result === 'success' && result.data) {
        setProperties(result.data);
        setError(null);
      } else {
        setError(result.message || '찜 목록을 불러올 수 없습니다.');
      }
    } catch (err) {
      if (err.message.includes('401')) {
        setError('로그인이 필요합니다.');
      } else {
        setError('찜 목록을 불러오는 중 오류가 발생했습니다.');
      }
      console.error('Error fetching wishlist:', err);
    } finally {
      setLoading(false);
    }
  };

  // 컴포넌트 마운트 시 현재 로그인한 사용자의 찜 목록 불러오기
  useEffect(() => {
    fetchCurrentUserWishlist();

    // 로그인 상태 변경 감지 (Navbar에서 로그인한 경우)
    const handleUserInfoChanged = () => {
      fetchCurrentUserWishlist();
    };

    window.addEventListener('userInfoChanged', handleUserInfoChanged);

    return () => {
      window.removeEventListener('userInfoChanged', handleUserInfoChanged);
    };
  }, []);

  return (
    <div className="compare-page">
      <Navbar />
      
      <div className="compare-container">
        <div className="compare-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {/* 안내 아이콘 및 툴팁 */}
            <div style={{ position: 'relative', marginRight: '8px' }}>
              <span
                style={{ cursor: 'pointer', fontSize: '20px' }}
                onMouseEnter={e => {
                  const tooltip = e.currentTarget.nextSibling;
                  if (tooltip) tooltip.style.display = 'block';
                }}
                onMouseLeave={e => {
                  const tooltip = e.currentTarget.nextSibling;
                  if (tooltip) tooltip.style.display = 'none';
                }}
              >ℹ️</span>
              <div
                style={{
                  display: 'none',
                  position: 'absolute',
                  left: 0,
                  top: '40px',
                  background: '#fff',
                  border: '1px solid #ccc',
                  borderRadius: '6px',
                  padding: '6px 24px',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
                  zIndex: 10,
                  minWidth: '360px', // 180px * 2
                  maxWidth: '600px',
                  fontSize: '13px',
                  color: '#333',
                  overflow: 'auto'
                }}
              >
                <span>
                  매물들의 평균에 대한 평균 대비+-를 나타냅니다.<br />
                  단, 금액은 전세, 월세마다 각각의 평균 값을 매깁니다.
                </span>
              </div>
            </div>
            <h1 style={{ margin: 0 }}>찜 목록</h1>
            <p style={{ margin: 0 }}>나의 찜 목록을 확인하고 비교해보세요</p>
          </div>
        </div>

        <div className="compare-content">
          <div className="compare-left">
            {loading ? (
              <div className="loading">찜 목록을 불러오는 중...</div>
            ) : error ? (
              <div className="error-container">
                <div className="error">{error}</div>
                {error.includes('로그인') && (
                  <div className="login-prompt">
                    <p>찜 목록을 확인하려면 로그인해주세요.</p>
                    <button 
                      onClick={handleLoginClick}
                      className="login-btn"
                    >
                      로그인하기
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <Showlist 
                properties={properties} 
                selectedProperty={selectedProperty}
                selectProperty={selectProperty}
                isLoggedIn={isLoggedIn()}
                layout="horizontal"
                onWishlistChange={fetchCurrentUserWishlist}
              />
            )}
          </div>
          
          <div className="compare-right">
            <Chatbot 
              updateProperties={updateProperties} 
              onWishlistUpdate={handleWishlistUpdate}
              fullHeight={true} 
            />
          </div>
        </div>
      </div>
    </div>
  );
}
