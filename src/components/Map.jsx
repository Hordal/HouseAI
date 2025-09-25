import React, { useEffect, useRef, useCallback } from 'react';

const KAKAO_MAP_APPKEY = '21f14d148232db893c1c50c84ea76bf1';


const Map = ({ properties, selectProperty }) => {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef([]);
  const infoWindowsRef = useRef([]); // 인포윈도우 참조 추가

  // 기존 마커들을 제거하는 함수
  const clearMarkers = useCallback(() => {
    markersRef.current.forEach(marker => marker.setMap(null));
    markersRef.current = [];
    // 인포윈도우도 닫기
    infoWindowsRef.current.forEach(item => item.infoWindow.close());
    infoWindowsRef.current = [];
  }, []);

  // 매물 마커를 추가하는 함수
  const addPropertyMarkers = useCallback((map) => {
    console.log('🗺️ addPropertyMarkers 호출됨');
    console.log('🗺️ 현재 properties:', properties);
    
    clearMarkers();
    infoWindowsRef.current = [];
    
    if (!properties || properties.length === 0) {
      console.log('❌ 매물 데이터가 없음');
      return;
    }

    console.log('🗺️ 지도에 매물 마커 추가:', properties.length, '개');
    
    let validProperties = 0;
    properties.forEach((property, index) => {
      console.log(`🏠 매물 ${index + 1}:`, {
        aptNm: property.aptNm,
        lat: property.lat,
        lng: property.lng,
        latType: typeof property.lat,
        lngType: typeof property.lng
      });
      
      if (property.lat && property.lng) {
        validProperties++;
        const lat = parseFloat(property.lat);
        const lng = parseFloat(property.lng);
        
        if (isNaN(lat) || isNaN(lng)) {
          console.error('❌ 유효하지 않은 좌표:', { lat: property.lat, lng: property.lng });
          return;
        }
        
        console.log(`✅ 유효한 좌표로 마커 생성: ${lat}, ${lng}`);
        const position = new window.kakao.maps.LatLng(lat, lng);
        
        // 마커 생성 (모든 마커 동일한 기본 마커로)
        const marker = new window.kakao.maps.Marker({
          position: position,
          map: map
        });

        // 인포윈도우 생성
        const infoWindow = new window.kakao.maps.InfoWindow({
          content: `
            <div style="padding:10px; min-width:200px; font-size:12px;">
              <strong>${property.aptNm || '아파트명 없음'}</strong><br/>
              <span style="color:#666;">${property.jibun || ''}</span><br/>
              <span style="color:#007bff; font-weight:bold;">
                전세 ${property.deposit ? `${parseInt(property.deposit/10000)}억` : '정보없음'}
                ${property.monthlyRent && property.monthlyRent > 0 ? ` / 월세 ${property.monthlyRent}만원` : ''}
              </span><br/>
              <span style="color:#666;">${property.floor || ''}층</span>
              ${property.nearest_station ? `<br/><span style="color:#28a745;">🚇 ${property.nearest_station} ${property.station_distance || ''}</span>` : ''}
            </div>
          `
        });
        infoWindowsRef.current.push({ property, marker, infoWindow });


        // 마커 클릭 시 해당 매물로 스크롤하는 함수
        function scrollToProperty(property) {
          const houseId = property._id || property.id;
          if (!houseId) return;
          const el = document.getElementById(`property-${houseId}`);
          if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            // 선택 효과 강조(선택된 property에 이미 selected 클래스가 있음)
          }
        }

        window.kakao.maps.event.addListener(marker, 'click', () => {
          console.log('🏠 마커 클릭:', property);
          // 모든 인포윈도우 닫기
          infoWindowsRef.current.forEach(item => item.infoWindow.close());
          // 클릭한 마커의 인포윈도우만 열기
          infoWindow.open(map, marker);
          // Showlist의 selectedProperty만 변경
          if (typeof selectProperty === 'function') {
            selectProperty(property);
          }
          // 해당 매물로 스크롤
          scrollToProperty(property);
        });

        markersRef.current.push(marker);
        console.log(`✅ 마커 추가됨. 현재 마커 수: ${markersRef.current.length}`);
      } else {
        console.log(`❌ 매물 ${index + 1}에 좌표 정보 없음:`, property);
      }
    });
    
    console.log(`🎯 총 ${validProperties}개의 유효한 매물 마커가 생성됨`);

    // 매물이 있는 경우 첫 번째 매물 위치로 지도 중심 이동
    if (validProperties > 0 && properties[0].lat && properties[0].lng) {
      const lat = parseFloat(properties[0].lat);
      const lng = parseFloat(properties[0].lng);
      if (!isNaN(lat) && !isNaN(lng)) {
        const firstPropertyPosition = new window.kakao.maps.LatLng(lat, lng);
        map.setCenter(firstPropertyPosition);
        map.setLevel(6); // 줌 레벨을 조정하여 여러 매물을 볼 수 있도록
        console.log(`🎯 지도 중심을 첫 번째 매물로 이동: ${lat}, ${lng}`);
      }
    }
  }, [properties, selectProperty, clearMarkers]);
  // selectedProperty가 바뀔 때 인포윈도우 자동 오픈 로직 제거 (마커 클릭 시 바로 오픈)

  // 지도 생성 함수를 useCallback으로 메모이제이션
  const createMap = useCallback(() => {
    if (mapRef.current) {
      mapRef.current.innerHTML = ''; // 기존 지도 제거
      const options = {
        center: new window.kakao.maps.LatLng(37.56839, 126.98272),
        level: 3,
        mapTypeId: window.kakao.maps.MapTypeId.ROADMAP,
      };
      const map = new window.kakao.maps.Map(mapRef.current, options);
      mapInstanceRef.current = map;
      
      // 매물 마커 추가
      addPropertyMarkers(map);
    }
  }, [addPropertyMarkers]);

  // 카카오 맵 스크립트 로드 함수를 useCallback으로 메모이제이션
  const loadKakaoMapScript = useCallback(() => {
    const script = document.createElement('script');
    script.src = `//dapi.kakao.com/v2/maps/sdk.js?appkey=${KAKAO_MAP_APPKEY}&autoload=false`;
    script.async = true;
    script.onload = () => {
      window.kakao.maps.load(createMap);
    };
    document.head.appendChild(script);
  }, [createMap]);

  useEffect(() => {
    // 스크립트가 이미 있으면 추가하지 않음
    if (!window.kakao || !window.kakao.maps) {
      loadKakaoMapScript();
    } else {
      // 이미 스크립트가 로드된 경우 바로 지도 생성
      createMap();
    }
    
    // clean-up: 필요시 지도 영역 비우기
    const mapDiv = mapRef.current; // ref 값을 변수에 저장
    return () => {
      clearMarkers();
      if (mapDiv) mapDiv.innerHTML = '';
    };
  }, [createMap, loadKakaoMapScript, clearMarkers]);

  // 매물 데이터가 변경될 때마다 마커 업데이트
  useEffect(() => {
    if (mapInstanceRef.current && window.kakao && window.kakao.maps) {
      console.log('🔄 매물 데이터 변경 감지, 마커 업데이트');
      addPropertyMarkers(mapInstanceRef.current);
    }
  }, [properties, addPropertyMarkers]);

  return <div ref={mapRef} id="map" style={{ width: '100vw', height: '100vh', margin: 0, padding: 0 }}></div>;
};

export default Map;
