import os
import re
import httpx
from typing import List, Optional


KAKAO_API_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
NAVER_API_URL = "https://openapi.naver.com/v1/search/local.json"


async def search_restaurant(query: str, page: int = 1) -> dict:
    """카카오 → 네이버 순으로 식당 검색합니다."""
    kakao_key = os.getenv("KAKAO_API_KEY", "")
    naver_id = os.getenv("NAVER_CLIENT_ID", "")
    naver_secret = os.getenv("NAVER_CLIENT_SECRET", "")

    # 카카오 시도
    if kakao_key and kakao_key != "여기에_카카오_REST_API_키_입력":
        try:
            result = await _search_kakao(query, kakao_key, page)
            if result["results"]:
                return result
        except Exception as e:
            print(f"[카카오 API 실패, 네이버로 전환] {e}")

    # 네이버 시도
    if naver_id and naver_secret:
        try:
            return await _search_naver(query, naver_id, naver_secret)
        except Exception as e:
            raise ValueError(f"네이버 API 오류: {e}")

    raise ValueError(
        "검색 API 키가 없습니다.\n"
        "네이버 검색 API를 추천합니다 (무료, 설정 간단):\n"
        "1. developers.naver.com 접속 → 애플리케이션 등록\n"
        "2. '검색' API 추가\n"
        "3. .env에 NAVER_CLIENT_ID, NAVER_CLIENT_SECRET 입력"
    )


async def _search_kakao(query: str, api_key: str, page: int) -> dict:
    headers = {"Authorization": f"KakaoAK {api_key}"}
    params = {"query": query, "size": 5, "page": page}

    async with httpx.AsyncClient() as client:
        response = await client.get(KAKAO_API_URL, headers=headers, params=params)

        if response.status_code == 403:
            raise ValueError(
                "카카오 API 403: 카카오 개발자 콘솔 → 제품 설정 → 카카오맵 → 활성화 필요"
            )
        response.raise_for_status()
        data = response.json()

    return {
        "results": [
            {
                "id": p.get("id"),
                "name": p.get("place_name"),
                "category": p.get("category_name"),
                "address": p.get("road_address_name") or p.get("address_name"),
                "phone": p.get("phone"),
                "url": p.get("place_url"),
            }
            for p in data.get("documents", [])
        ],
        "total": data.get("meta", {}).get("total_count", 0),
        "source": "kakao",
    }


async def _search_naver(query: str, client_id: str, client_secret: str) -> dict:
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {"query": query + " 맛집", "display": 5, "sort": "comment"}

    async with httpx.AsyncClient() as client:
        response = await client.get(NAVER_API_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

    results = []
    for item in data.get("items", []):
        # 네이버 API는 HTML 태그 포함 → 제거
        name = re.sub(r"<[^>]+>", "", item.get("title", ""))
        results.append({
            "id": item.get("mapx"),
            "name": name,
            "category": item.get("category", ""),
            "address": item.get("roadAddress") or item.get("address", ""),
            "phone": item.get("telephone", ""),
            "url": item.get("link", ""),
        })

    return {
        "results": results,
        "total": data.get("total", 0),
        "source": "naver",
    }
