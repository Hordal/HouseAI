import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./StartSection.css";
import talkImage from "../asset/TALK.png"; // TALK 이미지 import

export default function StartSection() {
  const navigate = useNavigate();
  const [userInfo, setUserInfo] = useState(null);

  useEffect(() => {
    // 로그인 상태 확인
    const checkLoginStatus = () => {
      const savedUserInfo = localStorage.getItem('userInfo');
      if (savedUserInfo) {
        try {
          const parsedUserInfo = JSON.parse(savedUserInfo);
          if (parsedUserInfo.isLoggedIn) {
            setUserInfo(parsedUserInfo);
          } else {
            setUserInfo(null);
          }
        } catch {
          // JSON 파싱 오류 시 로그아웃 처리
          localStorage.removeItem('userInfo');
          setUserInfo(null);
        }
      } else {
        // localStorage에 userInfo가 없으면 로그아웃 상태
        setUserInfo(null);
      }
    };

    checkLoginStatus();

    // localStorage 변경 감지
    const handleStorageChange = (e) => {
      if (e.key === 'userInfo') {
        checkLoginStatus();
      }
    };

    // 커스텀 이벤트 감지 (로그인/로그아웃 시)
    const handleUserInfoChanged = () => {
      checkLoginStatus();
    };

    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('userInfoChanged', handleUserInfoChanged);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('userInfoChanged', handleUserInfoChanged);
    };
  }, []);

  return (
    <div className="start-section">
      <div className="start-title">
        집 <img src={talkImage} alt="TALK" className="start-title-ai-img" />
      </div>
      
      {userInfo ? (
        // 로그인된 상태 - 검색하기와 비교하기 버튼
        <div className="logged-in-buttons">
          <button
            className="start-btn search-btn"
            onClick={() => navigate('/dashboard')}
          >
            검색하기
          </button>
          <button
            className="start-btn compare-btn"
            onClick={() => navigate('/compare')}
          >
            찜 목록
          </button>
        </div>
      ) : (
        // 로그인되지 않은 상태 - 시작하기 버튼
        <button
          className="start-btn"
          onClick={() => navigate('/dashboard')}
        >
          시작하기
        </button>
      )}
    </div>
  );
}
