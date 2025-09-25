import React, { useState, useEffect } from "react";
import Navbar from "../components/Navbar";
import Map from "../components/Map";
import Chatbot from "../components/Chatbot";
import Showlist from "../components/Showlist";

export default function Dashboard() {
  // 매물 데이터 상태 관리
  const [properties, setProperties] = useState([]);
  const [selectedProperty, setSelectedProperty] = useState(null);
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  // 로그인 상태 확인
  useEffect(() => {
    const checkLoginStatus = () => {
      const userInfo = localStorage.getItem('userInfo');
      if (userInfo) {
        try {
          const parsedUserInfo = JSON.parse(userInfo);
          setIsLoggedIn(parsedUserInfo.isLoggedIn || false);
        } catch (error) {
          console.error('Failed to parse userInfo:', error);
          setIsLoggedIn(false);
        }
      } else {
        setIsLoggedIn(false);
      }
    };

    // 초기 로그인 상태 확인
    checkLoginStatus();

    // 로그인 상태 변경 감지
    const handleUserInfoChanged = () => {
      checkLoginStatus();
    };

    window.addEventListener('userInfoChanged', handleUserInfoChanged);
    window.addEventListener('storage', handleUserInfoChanged);

    return () => {
      window.removeEventListener('userInfoChanged', handleUserInfoChanged);
      window.removeEventListener('storage', handleUserInfoChanged);
    };
  }, []);

  // 매물 데이터 업데이트 함수
  const updateProperties = (newProperties) => {
    console.log('🏠 매물 데이터 업데이트:', newProperties);
    setProperties(newProperties);
  };

  // 매물 선택 함수
  const selectProperty = (property) => {
    setSelectedProperty(property);
  };

  // 컴포넌트가 마운트될 때 body 스크롤 숨기기
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    document.documentElement.style.overflow = 'hidden';
    document.body.style.margin = '0';
    document.body.style.padding = '0';
    document.documentElement.style.margin = '0';
    document.documentElement.style.padding = '0';
    
    // 컴포넌트가 언마운트될 때 원래대로 복구
    return () => {
      document.body.style.overflow = 'auto';
      document.documentElement.style.overflow = 'auto';
      document.body.style.margin = '';
      document.body.style.padding = '';
      document.documentElement.style.margin = '';
      document.documentElement.style.padding = '';
    };
  }, []);

  return (
    <>
      <Navbar />
      <div style={{ 
        position: "fixed",
        top: 0,
        left: 0,
        width: "100vw", 
        height: "100vh", 
        margin: 0, 
        padding: 0, 
        overflow: "hidden"
      }}>
        <Map 
          properties={properties}
          selectedProperty={selectedProperty}
          selectProperty={selectProperty}
        />
        
        {/* Showlist를 왼쪽에 지도 위에 오버레이로 배치 */}
        <div style={{
          position: "absolute",
          top: "80px",
          left: "20px",
          zIndex: 100,
          backgroundColor: "rgba(255, 255, 255, 0.95)",
          borderRadius: "12px",
          boxShadow: "0 4px 12px rgba(0, 0, 0, 0.15)",
          maxHeight: "calc(100vh - 120px)",
          overflowY: "auto",
          maxWidth: "702px"
        }}>
          <Showlist 
            properties={properties}
            selectedProperty={selectedProperty}
            selectProperty={selectProperty}
            isLoggedIn={isLoggedIn}
          />
        </div>

        <Chatbot 
          updateProperties={updateProperties}
        />
      </div>
    </>
  );
}
