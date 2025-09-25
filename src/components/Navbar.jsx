import React, { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import "./Navbar.css";

export default function Navbar({ onIntro, onGuide, onBusiness }) {
  const [userInfo, setUserInfo] = useState(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // JWT 토큰이 만료되었는지 확인하는 함수
    const isTokenExpired = (token) => {
      if (!token) return true;
      
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        const currentTime = Date.now() / 1000;
        return payload.exp < currentTime;
      } catch {
        return true;
      }
    };

    // 액세스 토큰 갱신 함수
    const refreshAccessToken = async (refreshToken) => {
      try {
        const response = await fetch('http://localhost:8000/token/refresh', {
          method: 'POST',
          headers: {
            'Content-Type': 'text/plain',
          },
          body: refreshToken,
        });

        if (response.ok) {
          const result = await response.json();
          return result.access_token;
        } else {
          throw new Error('Token refresh failed');
        }
      } catch (error) {
        console.error('Token refresh error:', error);
        throw error;
      }
    };

    // 로그인 상태 확인 및 토큰 갱신
    const validateAndRefreshTokens = async (savedUserInfo) => {
      const parsedUserInfo = JSON.parse(savedUserInfo);
      
      if (!parsedUserInfo.isLoggedIn) {
        return null;
      }

      // 액세스 토큰이 만료되었는지 확인
      if (isTokenExpired(parsedUserInfo.accessToken)) {
        // 리프레시 토큰도 만료되었으면 로그아웃
        if (isTokenExpired(parsedUserInfo.refreshToken)) {
          localStorage.removeItem('userInfo');
          return null;
        }
        
        // 액세스 토큰 갱신 시도
        try {
          const newAccessToken = await refreshAccessToken(parsedUserInfo.refreshToken);
          const updatedUserInfo = {
            ...parsedUserInfo,
            accessToken: newAccessToken,
            loginTime: new Date().toISOString()
          };
          localStorage.setItem('userInfo', JSON.stringify(updatedUserInfo));
          return updatedUserInfo;
        } catch {
          // 토큰 갱신 실패 시 로그아웃
          localStorage.removeItem('userInfo');
          return null;
        }
      }
      
      return parsedUserInfo;
    };

    // 컴포넌트 마운트 시 localStorage에서 사용자 정보 확인 및 토큰 검증
    const checkLoginStatus = async () => {
      const savedUserInfo = localStorage.getItem('userInfo');
      if (savedUserInfo) {
        try {
          const validUserInfo = await validateAndRefreshTokens(savedUserInfo);
          if (validUserInfo) {
            setUserInfo(validUserInfo);
          }
        } catch {
          localStorage.removeItem('userInfo');
        }
      }
    };

    checkLoginStatus();

    // localStorage 변경 감지 (다른 탭이나 팝업에서 로그인한 경우)
    const handleStorageChange = (e) => {
      if (e.key === 'userInfo') {
        checkLoginStatus();
      }
    };

    // 커스텀 이벤트 감지 (같은 페이지에서 로그인한 경우)
    const handleUserInfoChanged = () => {
      checkLoginStatus();
    };

    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('userInfoChanged', handleUserInfoChanged);

    // 주기적으로 토큰 상태 확인 (5분마다)
    const tokenCheckInterval = setInterval(checkLoginStatus, 5 * 60 * 1000);

    return () => {
      clearInterval(tokenCheckInterval);
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('userInfoChanged', handleUserInfoChanged);
    };
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('userInfo');
    setUserInfo(null);
    
    // 다른 컴포넌트에 로그아웃을 알리는 커스텀 이벤트 발생
    window.dispatchEvent(new Event('userInfoChanged'));
  };

  const handleLogin = () => {
    const width = 600;
    const height = 800;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;
    
    const popup = window.open(
      '/login',
      'loginWindow',
      `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes`
    );

    // 팝업에서 메시지 수신 대기
    const messageHandler = (event) => {
      if (event.data.type === 'LOGIN_SUCCESS') {
        setUserInfo(event.data.userInfo);
        popup.close();
        window.removeEventListener('message', messageHandler);
        
        // 다른 컴포넌트에 로그인 성공을 알리는 커스텀 이벤트 발생
        window.dispatchEvent(new Event('userInfoChanged'));
      }
    };
    
    window.addEventListener('message', messageHandler);
  };

  const handleSignup = () => {
    const width = 600;
    const height = 800;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;
    
    const popup = window.open(
      '/signup',
      'signupWindow',
      `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes`
    );

    // 팝업에서 메시지 수신 대기
    const messageHandler = (event) => {
      if (event.data.type === 'SIGNUP_SUCCESS') {
        popup.close();
        window.removeEventListener('message', messageHandler);
        // 회원가입 성공 후 로그인 페이지 팝업 열기
        handleLogin();
      }
    };
    
    window.addEventListener('message', messageHandler);
  };

  const handleCompare = () => {
    navigate('/compare');
  };

  const handleSearch = () => {
    navigate('/dashboard');
  };

  // Dashboard 페이지인지 확인
  const isDashboard = location.pathname === '/dashboard';
  // Compare 페이지인지 확인
  const isCompare = location.pathname === '/compare';

  return (
    <nav className="navbar">
      <button
        className="navbar-title"
        onClick={() => navigate('/')}
      >
        집TALK
      </button>
      <div className="navbar-btn-group">
        {onIntro && (
          <button className="navbar-btn" onClick={onIntro}>
            소개
          </button>
        )}
        {onGuide && (
          <button className="navbar-btn" onClick={onGuide}>
            가이드
          </button>
        )}
        {onBusiness && (
          <button className="navbar-btn" onClick={onBusiness}>
            비즈니스 정보
          </button>
        )}
        
        {userInfo ? (
          // 로그인된 상태
          <>
            {isDashboard && (
              <button
                className="navbar-btn compare-btn"
                onClick={handleCompare}
              >
                찜 목록
              </button>
            )}
            {isCompare && (
              <button
                className="navbar-btn search-btn"
                onClick={handleSearch}
              >
                검색하기
              </button>
            )}
            <span className="navbar-user-name">
              {userInfo.name}님
            </span>
            <button
              className="navbar-btn"
              onClick={handleLogout}
            >
              로그아웃
            </button>
          </>
        ) : (
          // 로그인되지 않은 상태
          <>
            <button
              className="navbar-btn"
              onClick={handleLogin}
            >
              로그인
            </button>
            <button
              className="navbar-btn"
              onClick={handleSignup}
            >
              회원가입
            </button>
          </>
        )}
      </div>
    </nav>
  );
}
