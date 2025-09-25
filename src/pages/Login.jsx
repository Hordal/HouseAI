import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import "../styles/login.css";

const Login = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");

    try {
      const response = await fetch("http://localhost:8000/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: email,
          password: password,
        }),
      });

      const result = await response.json();

      if (response.ok) {
        // 로그인 성공 시 JWT 토큰과 사용자 정보를 localStorage에 저장
        const userInfo = {
          isLoggedIn: true,
          name: result.user?.name || email.split('@')[0],
          email: result.user?.email || email,
          userId: result.user?.user_id,
          accessToken: result.access_token,
          refreshToken: result.refresh_token,
          loginTime: new Date().toISOString()
        };
        localStorage.setItem('userInfo', JSON.stringify(userInfo));
        
        // 팝업 창인지 확인
        if (window.opener) {
          // 부모 창에 로그인 성공 메시지 전송
          window.opener.postMessage({ type: 'LOGIN_SUCCESS', userInfo }, '*');
          window.close();
        } else {
          // 일반 페이지인 경우 대시보드로 이동
          navigate('/dashboard');
        }
      } else {
        // 로그인 실패 시 메시지 표시
        setError(result.detail || "로그인에 실패했습니다. 이메일과 비밀번호를 확인해주세요.");
      }
    } catch (error) {
      setError("네트워크 오류가 발생했습니다. 다시 시도해주세요.");
      console.error("Login error:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container">
      <h2>Login</h2>
      <form id="login-form" onSubmit={handleSubmit}>
        <input 
          type="email" 
          placeholder="이메일" 
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required 
        />
        <input 
          type="password" 
          placeholder="비밀번호" 
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required 
        />

        <button type="submit" className="login-button" disabled={isLoading}>
          {isLoading ? "로그인 중..." : "로그인"}
        </button>

        {error && (
          <div className="error-message" style={{
            color: 'red', 
            marginTop: '10px', 
            fontSize: '14px',
            textAlign: 'center'
          }}>
            {error}
          </div>
        )}

        <div className="link-row">
          <button 
            type="button"
            onClick={() => {
              if (window.opener) {
                // 팝업에서 회원가입 팝업 열기
                const width = 600;
                const height = 800;
                const left = window.screenX + (window.outerWidth - width) / 2;
                const top = window.screenY + (window.outerHeight - height) / 2;
                window.open('/signup', 'signupWindow', `width=${width},height=${height},left=${left},top=${top}`);
                window.close();
              } else {
                navigate('/signup');
              }
            }}
            style={{ background: 'none', border: 'none', color: '#007bff', cursor: 'pointer' }}
          >
            회원가입
          </button>
          <span>|</span>
          <a href="#">아이디 · 비밀번호 찾기</a>
        </div>
      </form>
    </div>
  );
};

export default Login;
