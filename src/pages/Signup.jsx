import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import "../styles/login.css";

const Signup = () => {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [agreed, setAgreed] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");

    // 비밀번호 확인
    if (password !== confirmPassword) {
      setError("비밀번호가 일치하지 않습니다.");
      setIsLoading(false);
      return;
    }

    // 약관 동의 확인
    if (!agreed) {
      setError("이용약관에 동의해주세요.");
      setIsLoading(false);
      return;
    }

    try {
      const response = await fetch("http://localhost:8000/signup", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: name,
          email: email,
          password: password,
          terms_agreed: agreed,
        }),
      });

      const result = await response.json();

      if (response.ok) {
        // 회원가입 성공 시 처리
        if (window.opener) {
          // 팝업 창인 경우
          alert("회원가입이 완료되었습니다.");
          window.opener.postMessage({ type: 'SIGNUP_SUCCESS' }, '*');
          window.close();
        } else {
          // 일반 페이지인 경우 로그인 페이지로 이동
          alert("회원가입이 완료되었습니다. 로그인 페이지로 이동합니다.");
          navigate('/login');
        }
      } else {
        // 회원가입 실패 시 메시지 표시
        setError(result.detail || "회원가입에 실패했습니다. 다시 시도해주세요.");
      }
    } catch (error) {
      setError("네트워크 오류가 발생했습니다. 다시 시도해주세요.");
      console.error("Signup error:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container">
      <h2>회원가입</h2>
      <form id="register-form" onSubmit={handleSubmit}>
        <input 
          type="text" 
          placeholder="이름" 
          value={name}
          onChange={(e) => setName(e.target.value)}
          required 
        />
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
        <input 
          type="password" 
          placeholder="비밀번호 확인" 
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required 
        />

        <div className="checkbox-container">
          <input 
            type="checkbox" 
            id="agree" 
            checked={agreed}
            onChange={(e) => setAgreed(e.target.checked)}
            required 
          />
          <label htmlFor="agree">이용약관에 동의합니다</label>
        </div>

        <button type="submit" className="login-button" disabled={isLoading}>
          {isLoading ? "가입 중..." : "회원가입"}
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
                // 팝업에서 로그인 팝업 열기
                const width = 600;
                const height = 800;
                const left = window.screenX + (window.outerWidth - width) / 2;
                const top = window.screenY + (window.outerHeight - height) / 2;
                window.open('/login', 'loginWindow', `width=${width},height=${height},left=${left},top=${top}`);
                window.close();
              } else {
                navigate('/login');
              }
            }}
            style={{ background: 'none', border: 'none', color: '#007bff', cursor: 'pointer' }}
          >
            이미 계정이 있으신가요? 로그인
          </button>
        </div>
      </form>
    </div>
  );
};

export default Signup;
