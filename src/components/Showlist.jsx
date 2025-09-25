import React, { useState, useEffect } from 'react';
import { addToWishlist, removeFromWishlist, getCurrentUserWishlist } from '../services/api';
import './Showlist.css';

export default function SearchResults({ properties, selectedProperty, selectProperty, isLoggedIn, layout = 'vertical', onWishlistChange }) {
  const [wishlistLoading, setWishlistLoading] = useState({});
  const [userWishlist, setUserWishlist] = useState([]);
  const [wishlistLoaded, setWishlistLoaded] = useState(false);

  // 로그인 상태가 변경되거나 컴포넌트가 마운트될 때 찜 목록 조회
  useEffect(() => {
    const fetchWishlist = async () => {
      if (isLoggedIn) {
        try {
          const wishlistData = await getCurrentUserWishlist();
          if (wishlistData.result === 'success') {
            setUserWishlist(wishlistData.data || []);
          } else {
            setUserWishlist([]);
          }
        } catch (error) {
          console.error('찜 목록 조회 오류:', error);
          setUserWishlist([]);
        } finally {
          setWishlistLoaded(true);
        }
      } else {
        setUserWishlist([]);
        setWishlistLoaded(false);
      }
    };

    fetchWishlist();
  }, [isLoggedIn]);

  // 매물이 찜 목록에 있는지 확인하는 함수
  const isInWishlist = (property) => {
    const houseId = property._id || property.id;
    return userWishlist.some(wishItem => wishItem._id === houseId || wishItem.house_id === houseId);
  };

  const handlePropertyClick = (property) => {
    selectProperty(property);
    // 선택된 매물 로그
    console.log('🏠 매물 선택:', property);
  };

  const handleWishlistClick = async (property) => {
    const houseId = property._id || property.id;
    if (!houseId) {
      alert('매물 ID를 찾을 수 없습니다.');
      return;
    }

    const isCurrentlyInWishlist = isInWishlist(property);
    
    // 로딩 상태 설정
    setWishlistLoading(prev => ({ ...prev, [houseId]: true }));

    try {
      let result;
      
      if (isCurrentlyInWishlist) {
        // 찜 삭제
        result = await removeFromWishlist(houseId);
        if (result.result === 'success') {
          // 찜 목록에서 제거
          setUserWishlist(prev => prev.filter(item => 
            item._id !== houseId && item.house_id !== houseId
          ));
          // Compare 페이지에서 찜 목록 업데이트
          if (onWishlistChange) {
            onWishlistChange();
          }
        } else {
          alert(result.message || '찜 목록 삭제에 실패했습니다.');
        }
      } else {
        // 찜 추가
        result = await addToWishlist(houseId);
        if (result.result === 'success') {
          // 찜 목록에 추가 (간단한 형태로)
          setUserWishlist(prev => [...prev, { _id: houseId, house_id: houseId }]);
          // Compare 페이지에서 찜 목록 업데이트
          if (onWishlistChange) {
            onWishlistChange();
          }
        } else {
          alert(result.message || '찜 목록 추가에 실패했습니다.');
        }
      }
    } catch (error) {
      console.error('찜하기 오류:', error);
      
      if (error.message.includes('401')) {
        alert('로그인이 필요합니다. 다시 로그인해주세요.');
      } else if (error.message.includes('이미 찜한')) {
        alert('이미 찜한 매물입니다.');
      } else if (error.message.includes('찜 목록에 없음')) {
        alert('찜 목록에 없는 매물입니다.');
      } else {
        const action = isCurrentlyInWishlist ? '삭제' : '추가';
        alert(`찜하기 ${action}에 실패했습니다. 다시 시도해주세요.`);
      }
    } finally {
      // 로딩 상태 해제
      setWishlistLoading(prev => ({ ...prev, [houseId]: false }));
    }
  };

  // [역할] formatPrice: 만원 단위의 숫자(예: 4000=4천만, 40000=4억)를 정확하게 억/천만/만원 단위로 변환해주는 함수입니다.
  // 예시: 40000 -> '4억', 45000 -> '4억 5000만', 4000 -> '4천만', 12345 -> '1억 2천만 345만'
  const formatPrice = (price) => {
    if (!price) return '정보없음';
    
    const priceNum = parseInt(price);
    if (priceNum >= 10000) {
      const 억 = Math.floor(priceNum / 10000);
      const 만 = priceNum % 10000;
      if (만 === 0) {
        return `${억}억`;
      } else if (만 >= 1000) {
        const 천만 = Math.floor(만 / 1000);
        const 만_나머지 = 만 % 1000;
        if (만_나머지 === 0) {
          return `${억}억 ${천만}천만`;
        } else {
          return `${억}억 ${천만}천만 ${만_나머지}만`;
        }
      } else {
        return `${억}억 ${만}만`;
      }
    } else if (priceNum >= 1000) {
      const 천만 = Math.floor(priceNum / 1000);
      const 만_나머지 = priceNum % 1000;
      if (만_나머지 === 0) {
        return `${천만}천만`;
      } else {
        return `${천만}천만 ${만_나머지}만`;
      }
    } else {
      return `${priceNum}만`;
    }
  };

  const formatRentInfo = (deposit, monthlyRent) => {
    if (!deposit) return '정보없음';
    
    // monthlyRent가 0이거나 없으면 전세
    if (!monthlyRent || monthlyRent === 0) {
      return `전세 ${formatPrice(deposit)}`;
    }
    
    // monthlyRent가 있으면 보증금/월세 형태
    return `보증금 ${formatPrice(deposit)} / 월세 ${monthlyRent}만원`;
  };

  // 평균값 계산 (Compare 모드일 때만)
  let avg = {};
  let avgJeonse = 0, avgDeposit = 0, avgMonthlyRent = 0, avgDistance = 0, avgArea = 0;
  let jeonseList = [], depositList = [], monthlyList = [], distanceList = [], areaList = [];
  const isCompare = layout === 'horizontal' && properties.length > 0;
  if (isCompare) {
    properties.forEach(p => {
      if (!p.monthlyRent || p.monthlyRent === 0) {
        jeonseList.push(Number(p.deposit) || 0);
      } else {
        depositList.push(Number(p.deposit) || 0);
        monthlyList.push(Number(p.monthlyRent) || 0);
      }
      distanceList.push(Number(p.distance_to_station) || 0);
      areaList.push(Number(p.area_pyeong) || 0);
    });
    avgJeonse = jeonseList.length > 0 ? jeonseList.reduce((a,b)=>a+b,0)/jeonseList.length : 0;
    avgDeposit = depositList.length > 0 ? depositList.reduce((a,b)=>a+b,0)/depositList.length : 0;
    avgMonthlyRent = monthlyList.length > 0 ? monthlyList.reduce((a,b)=>a+b,0)/monthlyList.length : 0;
    avgDistance = distanceList.length > 0 ? distanceList.reduce((a,b)=>a+b,0)/distanceList.length : 0;
    avgArea = areaList.length > 0 ? areaList.reduce((a,b)=>a+b,0)/areaList.length : 0;
    avg = {
      jeonse: avgJeonse,
      deposit: avgDeposit,
      monthlyRent: avgMonthlyRent,
      distance_to_station: avgDistance,
      area_pyeong: avgArea
    };
  }

  return (
    <div className={`search-results-container ${layout === 'horizontal' ? 'horizontal-layout' : ''}`}>
      <h1 className="search-results-title">
        {layout === 'horizontal' ? '찜 목록' : '검색 결과'} ({properties.length}건)
      </h1>

      <div className={`search-results-list ${layout === 'horizontal' ? 'horizontal-list' : ''}`}>
        {properties.length === 0 ? (
          <div className="empty-state">
            {layout === 'horizontal' 
              ? '💭 찜한 매물이 없습니다. 채팅으로 원하는 매물을 찾아 찜해보세요!' 
              : '💭 채팅으로 원하는 매물을 검색해보세요!'
            }
          </div>
        ) : (
          properties.map((property, idx) => {
            const houseId = property._id || property.id;
            return (
              <div
                key={idx}
                id={`property-${houseId}`}
                onClick={() => handlePropertyClick(property)}
                className={`property-item ${layout === 'horizontal' ? 'horizontal-item' : ''} ${selectedProperty === property ? 'selected' : ''}`}
              >
              {layout === 'horizontal' && isLoggedIn && wishlistLoaded && (
                <button 
                  className={`wishlist-button-top ${isInWishlist(property) ? 'remove' : 'add'}`}
                  onClick={(e) => {
                    e.stopPropagation(); // 매물 클릭 이벤트 방지
                    handleWishlistClick(property);
                  }}
                  disabled={wishlistLoading[property._id || property.id]}
                >
                  {wishlistLoading[property._id || property.id] 
                    ? '⏳' 
                    : '❤️'
                  }
                </button>
              )}
              
              <div className="property-content">
                {/* 아파트명 */}
                <div className="property-name">
                  <b>아파트명:</b> <span style={{color: '#0d47a1', fontWeight: 'bold'}}>{property.aptNm || '아파트명 없음'}</span>
                </div>
                {/* 구 */}
                {layout === 'horizontal' && property.gu && (
                  <div className="property-extra"><b>구:</b> {property.gu}</div>
                )}
                {/* 동 */}
                {layout === 'horizontal' && property.dong && (
                  <div className="property-extra"><b>동:</b> {property.dong}</div>
                )}
                {/* 주소 */}
                <div className="property-address">
                  <b>주소:</b> {property.jibun || '주소 정보 없음'}
                </div>
                {/* 층수 */}
                <div className="property-floor">
                  <b>층수:</b> {property.floor !== undefined ? property.floor : '정보없음'}
                </div>
                {/* 가까운 역 */}
                <div className="property-station">
                  <b style={{color: '#333'}}>가장 가까운 역:</b> <span style={{color: property.nearest_station ? '#388e3c' : '#333'}}>{property.nearest_station || '정보없음'}</span>
                </div>
                {/* 역까지 거리 */}
                <div className="property-distance">
                  <b>역까지 거리:</b> {property.distance_to_station !== undefined ? Math.floor(Number(property.distance_to_station)) + 'm' : '정보없음'}
                  {isCompare && avg.distance_to_station ? (
                    (() => {
                      const diff = (property.distance_to_station !== undefined ? Math.floor(Number(property.distance_to_station)) - Math.floor(avg.distance_to_station) : 0);
                      const color = diff < 0 ? '#d32f2f' : diff > 0 ? '#1976d2' : '#333';
                      return (
                        <span style={{fontSize: '13px', color, marginLeft: '8px'}}>
                          {property.distance_to_station !== undefined ? (diff > 0 ? '+' : '') + diff + 'm' : ''}
                        </span>
                      );
                    })()
                  ) : null}
                </div>
                {/* 금액 */}
                <div className="property-price">
                  <b style={{color: '#333'}}>금액 :</b> <span style={{color: '#333'}}>{formatRentInfo(property.deposit, property.monthlyRent)}</span>
                  {isCompare && avg && (
                    <div style={{fontSize: '13px', marginTop: '4px'}}>
                      {/* 전세일 때 */}
                      {(!property.monthlyRent || property.monthlyRent === 0) && property.deposit !== undefined && avg.jeonse ?
                        (() => {
                          const diff = Number(property.deposit) - avg.jeonse;
                          const sign = diff > 0 ? '+' : diff < 0 ? '-' : '';
                          const absDiff = Math.abs(diff);
                          const 억 = Math.floor(absDiff / 10000);
                          const 만 = Math.round(absDiff % 10000);
                          let formatted = '';
                          if (억 > 0) formatted += `${sign}${억}억`;
                          if (만 > 0) formatted += (억 > 0 ? ' ' : sign) + `${만}만`;
                          if (억 === 0 && 만 === 0) formatted = sign + '0만';
                          const color = diff < 0 ? '#d32f2f' : diff > 0 ? '#1976d2' : '#333';
                          return <span style={{color}}>전세가: {formatted}</span>;
                        })()
                        : null}
                      {/* 월세일 때 */}
                      {(property.monthlyRent && property.monthlyRent > 0) && property.deposit !== undefined && avg.deposit ?
                        (() => {
                          const diff = Number(property.deposit) - avg.deposit;
                          const sign = diff > 0 ? '+' : diff < 0 ? '-' : '';
                          const absDiff = Math.abs(diff);
                          const 억 = Math.floor(absDiff / 10000);
                          const 만 = Math.round(absDiff % 10000);
                          let formatted = '';
                          if (억 > 0) formatted += `${sign}${억}억`;
                          if (만 > 0) formatted += (억 > 0 ? ' ' : sign) + `${만}만`;
                          if (억 === 0 && 만 === 0) formatted = sign + '0만';
                          const color = diff < 0 ? '#d32f2f' : diff > 0 ? '#1976d2' : '#333';
                          return <span style={{color}}>보증금: {formatted}</span>;
                        })()
                        : null}
                      {(property.monthlyRent && property.monthlyRent > 0) && property.monthlyRent !== undefined && avg.monthlyRent ?
                        (() => {
                          const diff = Number(property.monthlyRent) - avg.monthlyRent;
                          const color = diff < 0 ? '#d32f2f' : diff > 0 ? '#1976d2' : '#333';
                          return <span style={{marginLeft: '12px', color}}>
                            월세: {diff > 0 ? '+' : ''}{diff.toFixed(0)}만
                          </span>;
                        })()
                        : null}
                    </div>
                  )}
                </div>
                {/* 면적(평) */}
                {layout === 'horizontal' && property.area_pyeong && (
                  <div className="property-extra"><b>면적(평):</b> {property.area_pyeong}
                    {isCompare && avg.area_pyeong ? (
                      (() => {
                        const diff = Number(property.area_pyeong) - avg.area_pyeong;
                        const color = diff < 0 ? '#1976d2' : diff > 0 ? '#d32f2f' : '#333';
                        return (
                          <span style={{fontSize: '13px', color, marginLeft: '8px'}}>
                            {(diff > 0 ? '+' : '') + diff.toFixed(1)}평
                          </span>
                        );
                      })()
                    ) : null}
                  </div>
                )}
              </div>

              {layout !== 'horizontal' && isLoggedIn && wishlistLoaded && (
                <button 
                  className={`wishlist-button ${isInWishlist(property) ? 'remove' : 'add'}`}
                  onClick={(e) => {
                    e.stopPropagation(); // 매물 클릭 이벤트 방지
                    handleWishlistClick(property);
                  }}
                  disabled={wishlistLoading[property._id || property.id]}
                >
                  {wishlistLoading[property._id || property.id] 
                    ? '⏳' 
                    : (isInWishlist(property) ? '❤️' : '🤍')
                  }
                </button>
              )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
