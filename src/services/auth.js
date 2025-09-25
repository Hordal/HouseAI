// API 요청 시 자동으로 JWT 토큰을 헤더에 추가하는 유틸리티

/**
 * 현재 저장된 액세스 토큰을 가져옵니다
 */
export const getAccessToken = () => {
  try {
    const userInfo = localStorage.getItem('userInfo');
    if (userInfo) {
      const parsed = JSON.parse(userInfo);
      return parsed.accessToken;
    }
  } catch {
    return null;
  }
  return null;
};

/**
 * JWT 토큰이 만료되었는지 확인합니다
 */
export const isTokenExpired = (token) => {
  if (!token) return true;
  
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const currentTime = Date.now() / 1000;
    return payload.exp < currentTime;
  } catch {
    return true;
  }
};

/**
 * 인증이 필요한 API 요청을 보냅니다
 */
export const authenticatedFetch = async (url, options = {}) => {
  const token = getAccessToken();
  
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (token && !isTokenExpired(token)) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  // 401 Unauthorized인 경우 토큰 갱신 시도
  if (response.status === 401) {
    try {
      const userInfo = JSON.parse(localStorage.getItem('userInfo'));
      if (userInfo && userInfo.refreshToken && !isTokenExpired(userInfo.refreshToken)) {
        // 리프레시 토큰으로 새 액세스 토큰 발급
        const refreshResponse = await fetch('http://localhost:8000/token/refresh', {
          method: 'POST',
          headers: {
            'Content-Type': 'text/plain',
          },
          body: userInfo.refreshToken,
        });

        if (refreshResponse.ok) {
          const result = await refreshResponse.json();
          const updatedUserInfo = {
            ...userInfo,
            accessToken: result.access_token,
            loginTime: new Date().toISOString()
          };
          localStorage.setItem('userInfo', JSON.stringify(updatedUserInfo));

          // 새 토큰으로 원래 요청 재시도
          headers['Authorization'] = `Bearer ${result.access_token}`;
          return fetch(url, { ...options, headers });
        }
      }
    } catch (error) {
      console.error('Token refresh failed:', error);
    }
    
    // 토큰 갱신 실패 시 로그아웃
    localStorage.removeItem('userInfo');
    window.location.href = '/login';
  }

  return response;
};

/**
 * 로그아웃 처리
 */
export const logout = () => {
  localStorage.removeItem('userInfo');
  window.location.href = '/';
};

/**
 * 현재 로그인 상태 확인
 */
export const isLoggedIn = () => {
  try {
    const userInfo = localStorage.getItem('userInfo');
    if (userInfo) {
      const parsed = JSON.parse(userInfo);
      return parsed.isLoggedIn && !isTokenExpired(parsed.accessToken);
    }
  } catch {
    return false;
  }
  return false;
};

/**
 * 현재 사용자 정보 가져오기
 */
export const getCurrentUser = () => {
  try {
    const userInfo = localStorage.getItem('userInfo');
    if (userInfo) {
      const parsed = JSON.parse(userInfo);
      if (parsed.isLoggedIn && !isTokenExpired(parsed.accessToken)) {
        return parsed;
      }
    }
  } catch {
    return null;
  }
  return null;
};
