# tistory-restaurant-blogger

식당 사진 업로드 → Claude Vision 분석 → SEO 블로그 포스트 → 티스토리 자동 발행 웹앱

## 기능

- 카카오 API로 식당 검색 및 정보 조회
- 식사 사진 업로드 (다중)
- Claude Vision으로 사진 분석 + SEO 최적화 블로그 포스트 자동 생성
- 즉시 발행 또는 예약 발행 (인메모리 스케줄러)
- Playwright로 티스토리 자동 로그인 및 포스팅

## 설치

```bash
pip install -r requirements.txt
playwright install chromium
```

## 환경 변수

`.env` 파일 생성:

```env
ANTHROPIC_API_KEY=
KAKAO_REST_API_KEY=
TISTORY_EMAIL=
TISTORY_PASSWORD=
```

## 실행

```bash
python app.py
# 또는
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

브라우저에서 `http://localhost:8000` 접속

## 구조

```
tistory-restaurant-blogger/
├── app.py                    # FastAPI 앱
├── services/
│   ├── kakao_service.py      # 카카오 로컬 API
│   ├── claude_service.py     # Claude Vision + 블로그 생성
│   ├── image_service.py      # 이미지 리사이즈/저장
│   └── tistory_service.py    # Playwright 티스토리 포스팅
├── templates/index.html      # 프론트엔드 UI
└── static/app.js             # 클라이언트 스크립트
```

> 예약 발행은 서버 재시작 시 초기화됩니다.
