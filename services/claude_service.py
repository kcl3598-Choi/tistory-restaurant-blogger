import os
import base64
from pathlib import Path
from typing import List, Tuple
import anthropic


BLOG_TOOL = {
    "name": "save_blog_post",
    "description": "SEO 최적화된 맛집 블로그 포스트를 저장합니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "SEO 최적화 제목 (식당명+지역+음식종류 포함, 30-50자)",
            },
            "meta_description": {
                "type": "string",
                "description": "검색결과에 표시될 설명 (140-160자)",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "티스토리 태그 10-15개 (지역명, 음식종류, 식당명, 분위기 등)",
            },
            "category": {
                "type": "string",
                "description": "카테고리 (예: 맛집, 서울맛집, 강남맛집 등)",
            },
            "content": {
                "type": "string",
                "description": "마크다운 형식의 블로그 본문 (2500자 이상)",
            },
            "seo_keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "주요 SEO 키워드 목록",
            },
        },
        "required": ["title", "meta_description", "tags", "category", "content", "seo_keywords"],
    },
}

SYSTEM_PROMPT = """당신은 대한민국 최고의 맛집 전문 블로그 작가입니다.
실제 방문한 맛집 사진과 정보를 바탕으로 독자들이 실제로 방문하고 싶게 만드는 생생한 후기를 작성합니다.

## 2026 SEO 최적화 전략
1. **제목**: "[식당명] [지역] 맛집 후기 - [음식종류] (주차/웨이팅/가격 정보)" 형식
2. **롱테일 키워드**: "~맛집 추천", "~데이트 코스", "~혼밥 가능" 등을 자연스럽게 포함
3. **구조화된 콘텐츠**: H2/H3 헤딩으로 명확한 섹션 구분
4. **E-E-A-T 신호**: 실제 방문 경험, 구체적 메뉴명과 가격, 솔직한 평가
5. **검색 의도 충족**: 정보형("어디가 맛있나?") + 탐색형("~식당 어때?") 동시 충족

## 필수 포함 섹션
- **도입부**: 방문 동기와 첫인상 (감성적 서술)
- **식당 기본 정보**: 위치, 영업시간, 주차, 웨이팅, 가격대
- **메뉴 소개**: 주문한 메뉴별 상세 설명 (맛, 양, 가성비)
- **분위기/인테리어**: 매장 분위기, 좌석 구성
- **총평**: 장단점 솔직하게, 추천 대상 명시
- **방문 정보 표**: 주소, 영업시간, 전화번호, 주차 여부를 마크다운 표로

## 글쓰기 스타일
- 1인칭 후기 형식 ("~를 먹어봤어요", "~가 인상적이었어요")
- 구체적인 맛 묘사 (단순히 "맛있다" 대신 "불향이 가득한 부드러운 육즙")
- 사진 설명을 자연스럽게 본문에 녹여내기
- 독자가 실제로 주문할 수 있도록 메뉴 추천 명시"""


def _encode_image(image_path: str) -> Tuple[str, str]:
    """이미지를 base64로 인코딩하고 미디어 타입을 반환합니다."""
    path = Path(image_path)
    suffix = path.suffix.lower()
    media_type_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_type_map.get(suffix, "image/jpeg")

    with open(image_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")

    return data, media_type


async def analyze_photos(image_paths: List[str]) -> str:
    """사진들을 분석하여 음식 및 매장 묘사를 반환합니다."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    content = []
    for path in image_paths[:8]:  # 최대 8장
        data, media_type = _encode_image(path)
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": data},
        })

    content.append({
        "type": "text",
        "text": "이 맛집 사진들을 분석해주세요. 각 사진에서 보이는 음식명, 색감, 플레이팅, 양, 특징적인 부분과 매장 분위기를 상세히 묘사해주세요. 블로그 글 작성에 활용할 수 있도록 생생하게 설명해주세요.",
    })

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text


async def generate_blog_post(
    restaurant: dict,
    photo_analysis: str,
    visit_date: str = "",
    extra_notes: str = "",
) -> dict:
    """카카오 맛집 정보 + 사진 분석 결과로 SEO 최적화 블로그 글을 생성합니다."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    address = restaurant.get("address", "")
    # 지역 추출 (서울 강남구 → 강남)
    region = _extract_region(address)

    prompt = f"""다음 맛집 정보와 사진 분석을 바탕으로 SEO 최적화된 블로그 글을 작성해주세요.

## 식당 정보
- 식당명: {restaurant.get("name", "")}
- 카테고리: {restaurant.get("category", "")}
- 주소: {address}
- 지역: {region}
- 전화번호: {restaurant.get("phone", "정보 없음")}
- 카카오맵 URL: {restaurant.get("url", "")}
- 방문 날짜: {visit_date or "최근 방문"}

## 사진 분석 결과
{photo_analysis}

## 추가 메모 (선택)
{extra_notes or "없음"}

위 정보를 바탕으로 save_blog_post 도구를 사용하여 블로그 글을 저장해주세요.
제목에는 반드시 "{restaurant.get("name", "")} {region}" 이 포함되어야 합니다."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        tools=[BLOG_TOOL],
        tool_choice={"type": "tool", "name": "save_blog_post"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "save_blog_post":
            return block.input

    raise ValueError("블로그 글 생성에 실패했습니다.")


def _extract_region(address: str) -> str:
    """주소에서 지역명을 추출합니다."""
    if not address:
        return ""

    parts = address.split()
    # "서울특별시 강남구 ..." → "강남구" or "강남"
    for part in parts:
        if part.endswith("구") or part.endswith("시") or part.endswith("동"):
            cleaned = part.replace("구", "").replace("시", "").replace("동", "")
            return cleaned
    return parts[0] if parts else ""
