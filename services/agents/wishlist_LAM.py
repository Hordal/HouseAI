import re
from services.list_services import add_wish, delete_wish, get_wishlist

# 파일 상단에 유틸 함수 추가

def format_money(amount):
    try:
        amount = int(amount)
        if amount >= 10000:
            eok = amount // 10000
            man = amount % 10000
            if man == 0:
                return f"{eok}억"
            else:
                return f"{eok}억 {man:,}만원"
        else:
            return f"{amount:,}만원"
    except Exception:
        return str(amount)

class WishlistLAM:
    """
    사용자의 'N번 매물을 찜에 등록해줘' 또는 'N번 찜 삭제해줘' 요청을 처리하는 에이전트
    """

    def parse_numbers(self, user_query: str):
        """
        '1번, 2번, 3번' 등에서 [1, 2, 3] 추출
        """
        return [int(num) for num in re.findall(r'(\d+)번', user_query)]

    def handle_wishlist_request(self, user_query: str, user_id: int, search_results=None):
        """
        찜 관련 요청을 처리하는 메인 메서드 (다중 번호 지원)
        """
        from db.database import get_db
        db = next(get_db())
        try:
            # intent 파악
            is_view = any(keyword in user_query.lower() for keyword in ["찜 목록", "찜한 매물", "찜 조회", "찜 비교"])
            is_add = (not is_view) and any(word in user_query for word in ["찜", "등록", "추가"])
            is_remove = (not is_view) and any(word in user_query for word in ["삭제", "빼", "제거"])
            # 로그인 여부 확인 (None, 0, int가 아닌 경우 모두 차단)
            if not isinstance(user_id, int) or not user_id:
                return "❌ 로그인이 되어있지 않아 찜 기능 사용이 불가능합니다."

            # 1. 삭제/추가 명령 먼저 처리
            numbers = self.parse_numbers(user_query)
            # '검색결과에 있는' 문구가 있으면 검색결과 기준으로 삭제
            if numbers and any(word in user_query for word in ["삭제", "빼", "제거"]):
                # 1. '찜 목록에서'라는 문구가 있으면 → 찜 목록 기준 번호로 삭제
                if "찜 목록에서" in user_query:
                    wishlist_result = get_wishlist(db, user_id)
                    if not wishlist_result or wishlist_result.get("result") != "success":
                        return "📝 찜 목록이 비어있습니다."
                    wishlist = wishlist_result.get("data", [])
                    def name_key(house):
                        name = house.get('aptNm')
                        if name is None or name == '':
                            return chr(0x10FFFF)
                        return str(name)
                    wishlist = sorted(wishlist, key=name_key)
                    results = []
                    for number in numbers:
                        if number < 1 or number > len(wishlist):
                            results.append(f"❌ {number}번: 해당 번호의 매물이 없습니다.")
                            continue
                        house = wishlist[number - 1]
                        house_id = house.get("_id") or house.get("house_id")
                        result = delete_wish(db, user_id, house_id)
                        msg = f"✅ {number}번 매물 삭제" if result['result'] == 'success' else f"❌ {number}번: {result['message']}"
                        results.append(msg)
                    return "\n".join(results)
                # 2. '찜목록에서'라는 문구만 있으면 → 검색결과 기준 번호의 매물을 찜 목록에서 삭제
                elif "찜목록에서" in user_query:
                    if not search_results:
                        return "❌ 최근 검색결과가 없습니다."
                    results = []
                    for number in numbers:
                        if number < 1 or number > len(search_results):
                            results.append(f"❌ {number}번: 검색결과에 해당 매물이 없습니다.")
                            continue
                        house = search_results[number - 1]
                        house_id = house.get("_id") or house.get("house_id")
                        result = delete_wish(db, user_id, house_id)
                        msg = f"✅ 검색결과 {number}번 매물 삭제" if result['result'] == 'success' else f"❌ {number}번: {result['message']}"
                        results.append(msg)
                    return "\n".join(results)
                else:
                    # 기존대로 찜 목록 기준 번호로 삭제 (한 번만 불러와서 기준 고정)
                    wishlist_result = get_wishlist(db, user_id)
                    if not wishlist_result or wishlist_result.get("result") != "success":
                        return "📝 찜 목록이 비어있습니다."
                    wishlist = wishlist_result.get("data", [])
                    def name_key(house):
                        name = house.get('aptNm')
                        if name is None or name == '':
                            return chr(0x10FFFF)
                        return str(name)
                    wishlist = sorted(wishlist, key=name_key)
                    results = []
                    for number in numbers:
                        if number < 1 or number > len(wishlist):
                            results.append(f"❌ {number}번: 해당 번호의 매물이 없습니다.")
                            continue
                        house = wishlist[number - 1]
                        house_id = house.get("_id") or house.get("house_id")
                        result = delete_wish(db, user_id, house_id)
                        msg = f"✅ {number}번 매물 삭제" if result['result'] == 'success' else f"❌ {number}번: {result['message']}"
                        results.append(msg)
                    return "\n".join(results)
            # 다중 추가 복구
            if numbers and any(word in user_query for word in ["찜", "등록", "추가"]):
                results = []
                for number in numbers:
                    result = self.add_wish_by_number(db, user_id, number, search_results)
                    msg = f"✅ {number}번 매물 추가" if result['result'] == 'success' else f"❌ {number}번: {result['message']}"
                    results.append(msg)
                return "\n".join(results)

            # 기존 단일 처리(혹시라도 번호가 없을 때)
            add_number = self.parse_add_command(user_query)
            if add_number is not None:
                result = self.add_wish_by_number(db, user_id, add_number, search_results)
                if result["result"] == "success":
                    return f"✅ {add_number}번 매물을 찜 목록에 추가했습니다."
                else:
                    return f"❌ {result['message']}"

            remove_number = self.parse_remove_command(user_query)
            if remove_number is not None:
                result = self.remove_wish_by_number(db, user_id, remove_number, search_results)
                if result["result"] == "success":
                    return f"✅ {remove_number}번 매물을 찜 목록에서 삭제했습니다."
                else:
                    return f"❌ {result['message']}"

            # 2. 그 외에만 조회
            if any(keyword in user_query.lower() for keyword in ["찜 목록", "찜한 매물", "찜 조회", "찜 비교"]):
                return self.get_wishlist_response(db, user_id)

            # 일반적인 찜 관련 질문
            return "찜 관련 기능을 사용하려면 다음과 같이 말씀해주세요:\n• 'N번 매물을 찜에 등록해줘'\n• 'N번 찜 삭제해줘'\n• '찜 목록 보여줘'"
        except Exception as e:
            return f"❌ 처리 중 오류가 발생했습니다: {str(e)}"
        finally:
            db.close()

    def get_wishlist_response(self, db, user_id: int):
        """
        사용자의 찜 목록을 조회하고 응답을 생성
        """
        try:
            wishlist_result = get_wishlist(db, user_id)
            print("wishlist_result:", wishlist_result)  # 추가
            if not wishlist_result or wishlist_result.get("result") != "success":
                return "📝 찜 목록이 비어있습니다."
            wishlist = wishlist_result.get("data", [])
            response = f"💕 찜 목록 ({len(wishlist)}개)\n\n"
            # 항상 이름(aptNm) 오름차순 정렬 (이름 없는 매물은 맨 뒤)
            def name_key(house):
                name = house.get('aptNm')
                if name is None or name == '':
                    return chr(0x10FFFF)
                return str(name)
            wishlist = sorted(wishlist, key=name_key)
            for i, house in enumerate(wishlist, 1):
                rent_type = house.get('rent_type', '정보없음')
                deposit = house.get('deposit', house.get('보증금', 0))
                # 월세 필드명 보완
                rent = house.get('monthlyRent', house.get('rent', 0))
                apt_name = house.get('aptNm', '')
                floor = house.get('floor', '')
                address = (
                    house.get('address')
                    or house.get('full_address')
                    or house.get('road_address')
                    or house.get('jibun')
                    or house.get('aptNm')
                    or '주소 정보 없음'
                )
                station = house.get('nearest_station', '')
                distance = house.get('distance_to_station', '')
                # 거리 정수로 변환
                try:
                    if distance != '' and distance is not None:
                        distance = int(float(distance))
                    else:
                        distance = ''
                except Exception:
                    distance = ''
                deposit_str = format_money(deposit)
                rent_str = format_money(rent) if rent else None
                # 가격 정보 포맷팅
                if rent_type == '전세':
                    price_info = f"전세 : {deposit_str}"
                elif rent_type == '월세':
                    price_info = f"월세 : {deposit_str}/{rent_str if rent_str else '0원'}"
                else:
                    price_info = f"{rent_type} : {deposit_str}"
                # 매물명 옆에 층수
                apt_and_floor = f"{apt_name} {floor}층" if apt_name and floor else apt_name or address
                response += f"{i}. {apt_and_floor}\n"
                response += f"   {price_info}\n"
                # 지하철역+거리
                if station or distance:
                    station_info = f"🚉 {station}" if station else ''
                    distance_info = f"({distance}미터)" if distance != '' else ''
                    response += f"   {station_info} {distance_info}\n"
                response += "\n"
            # 안내 문구 제거
            # response += "💡 찜한 매물들을 비교하려면 '찜 목록 매물 비교해줘'라고 말씀해주세요."
            return response
        except Exception as e:
            print("wishlist error:", e)  # 추가
            return f"❌ 찜 목록 조회 중 오류가 발생했습니다: {str(e)}"

    def parse_add_command(self, user_query: str):
        """
        'N번' 패턴 추출 (예: '3번', '1번 매물')
        """
        match = re.search(r'(\d+)번', user_query)
        if match and ("찜" in user_query or "등록" in user_query or "추가" in user_query):
            return int(match.group(1))
        return None

    def parse_remove_command(self, user_query: str):
        """
        'N번' + '삭제'/'빼'/'제거' 패턴 추출
        """
        match = re.search(r'(\d+)번', user_query)
        if match and ("삭제" in user_query or "빼" in user_query or "제거" in user_query):
            return int(match.group(1))
        return None

    def add_wish_by_number(self, db, user_id, number, last_search_results):
        """
        검색결과 리스트에서 번호에 해당하는 house_id를 찾아 찜에 등록
        """
        if not last_search_results or number < 1 or number > len(last_search_results):
            return {"result": "fail", "message": "해당 번호의 매물이 없습니다."}
        house = last_search_results[number - 1]
        house_id = house.get("_id") or house.get("house_id")
        return add_wish(db, user_id, house_id)

    def remove_wish_by_number(self, db, user_id, number, last_search_results=None):
        """
        항상 최신 찜 목록을 불러와서 번호에 해당하는 house_id를 찾아 찜에서 삭제
        """
        wishlist_result = get_wishlist(db, user_id)
        if not wishlist_result or wishlist_result.get("result") != "success":
            return {"result": "fail", "message": "찜 목록이 비어있습니다."}
        wishlist = wishlist_result.get("data", [])
        # 이름순 정렬(찜 목록 보여주는 것과 동일하게)
        def name_key(house):
            name = house.get('aptNm')
            if name is None or name == '':
                return chr(0x10FFFF)
            return str(name)
        wishlist = sorted(wishlist, key=name_key)
        if number < 1 or number > len(wishlist):
            return {"result": "fail", "message": "해당 번호의 매물이 없습니다."}
        house = wishlist[number - 1]
        house_id = house.get("_id") or house.get("house_id")
        return delete_wish(db, user_id, house_id)
