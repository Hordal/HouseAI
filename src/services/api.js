import { authenticatedFetch } from './auth.js';

/**
 * 매물 검색 API
 */
export const searchProperties = async (query) => {
  try {
    const response = await authenticatedFetch('http://localhost:8000/search', {
      method: 'POST',
      body: JSON.stringify({ query }),
    });

    if (response.ok) {
      return await response.json();
    } else {
      throw new Error('Search failed');
    }
  } catch (error) {
    console.error('Search error:', error);
    throw error;
  }
};

/**
 * 채팅 API (WebSocket 대신 HTTP 요청인 경우)
 */
export const sendChatMessage = async (message) => {
  try {
    const response = await authenticatedFetch('http://localhost:8000/chat', {
      method: 'POST',
      body: JSON.stringify({ message }),
    });

    if (response.ok) {
      return await response.json();
    } else {
      throw new Error('Chat failed');
    }
  } catch (error) {
    console.error('Chat error:', error);
    throw error;
  }
};

/**
 * 사용자 정보 조회
 */
export const getUserProfile = async () => {
  try {
    const response = await authenticatedFetch('http://localhost:8000/user/profile');
    
    if (response.ok) {
      return await response.json();
    } else {
      throw new Error('Failed to get user profile');
    }
  } catch (error) {
    console.error('Get user profile error:', error);
    throw error;
  }
};

/**
 * 찜 목록에 매물 추가
 */
export const addToWishlist = async (houseId) => {
  try {
    const response = await authenticatedFetch('http://localhost:8000/wishlist/add', {
      method: 'POST',
      body: JSON.stringify({ house_id: houseId }),
    });

    if (response.ok) {
      return await response.json();
    } else {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to add to wishlist');
    }
  } catch (error) {
    console.error('Add to wishlist error:', error);
    throw error;
  }
};

/**
 * 찜 목록에서 매물 삭제
 */
export const removeFromWishlist = async (houseId) => {
  try {
    const response = await authenticatedFetch(`http://localhost:8000/wishlist/${houseId}`, {
      method: 'DELETE',
    });

    if (response.ok) {
      return await response.json();
    } else {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to remove from wishlist');
    }
  } catch (error) {
    console.error('Remove from wishlist error:', error);
    throw error;
  }
};

/**
 * 현재 로그인한 사용자의 찜 목록 조회
 */
export const getCurrentUserWishlist = async () => {
  try {
    const response = await authenticatedFetch('http://localhost:8000/wishlist');
    
    if (response.ok) {
      return await response.json();
    } else {
      throw new Error('Failed to get current user wishlist');
    }
  } catch (error) {
    console.error('Get current user wishlist error:', error);
    throw error;
  }
};

/**
 * 사용자 찜 목록 조회 (특정 user_id)
 */
export const getUserWishlist = async (userId) => {
  try {
    const response = await authenticatedFetch(`http://localhost:8000/user/${userId}/wishlist`);
    
    if (response.ok) {
      return await response.json();
    } else {
      throw new Error('Failed to get user wishlist');
    }
  } catch (error) {
    console.error('Get user wishlist error:', error);
    throw error;
  }
};
