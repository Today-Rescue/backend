# 오늘구조대 Backend

> 동네 빵집 사장님이 **매대 사진 한 장**으로 남은 빵을 세고, 마감 전에 팔고, 내일 얼마나 만들지 정하도록 돕는 서비스의 백엔드예요.

| | 주소 |
| --- | --- |
| 서비스 (프론트) | https://today-rescue.vercel.app |
| API 서버 | https://bakery-backend-bvvz.onrender.com/api/v1 |
| API 문서 (Swagger) | https://bakery-backend-bvvz.onrender.com/api/docs/ |
| 프론트 레포 | https://github.com/Today-Rescue/Front |

- 로그인 없이 데모 가게(`store_id = 1`)로 바로 사용할 수 있어요.
- Render 무료 서버라 한동안 요청이 없으면 잠들어요. **첫 요청은 30초~1분 걸릴 수 있어요.**

## 주요 기능

| 흐름 | 기능 | API |
| --- | --- | --- |
| 오전 | **매대 사진 인식**: 사진 한 장으로 품목별 개수 인식 (Gemini 비전, 품목 참고 사진 함께 비교) | `POST /stores/{id}/scans` |
| 오전 | 진열 기록: 확인·수정한 개수를 오늘 만든 수량으로 저장 | `POST /scans/{id}/confirm` |
| 마감 전 | **남을 위험도**: 마감까지 남은 시간·평소 판매 속도로 품목별 위험/주의/여유 판단 | `GET /scans/{id}/risk` |
| 마감 전 | **원터치 할인**: 위험·주의 품목만 골라 한 번에 할인 시작 | `POST /stores/{id}/campaigns/discount` |
| 마감 전 | **세트 판매**: 남은 빵으로 만들 수 있는 팩 구성 추천·계산 | `POST /stores/{id}/bundles/recommend` |
| 마감 전 | 세일 현황: 판매 진행률, 느린 품목에 할인율 올리기 제안 | `GET /stores/{id}/campaigns/live` |
| 마감 전 | 판매 확정: 팔린 수량 입력 → 남은 재고 차감 | `POST /campaigns/{id}/sales` |
| 마감 | 마감 기록: 남은 빵 처리(이월·폐기 등) 저장 | `PUT /stores/{id}/closings/{date}` |
| 다음 날 준비 | **내일 생산 추천**: 같은 요일 평균 → 비 예보 → 공휴일 → 마감 결과(완판·연속 남음·이월) 순서로 보정 | `GET /stores/{id}/recommendations` |
| 돌아보기 | 주간 대시보드·행동 타임라인·판매 달력 | `GET /stores/{id}/dashboard`, `/actions`, `/records/calendar` |

전체 API와 요청·응답 형식은 [Swagger](https://bakery-backend-bvvz.onrender.com/api/docs/)에서 볼 수 있어요.

## 외부 데이터

| 데이터 | 출처 | 쓰는 곳 |
| --- | --- | --- |
| 매대 사진 인식 | Google Gemini API | 스캔 |
| 강수확률·날씨 | 기상청 단기예보 (공공데이터포털) | 홈, 생산 추천 |
| 공휴일 | 한국천문연구원 특일 정보 (공공데이터포털) | 홈, 생산 추천 |
| 주소 → 좌표 | 카카오 로컬 API | 가게 등록 (기상청 격자 변환) |

## 기술 스택

- Python 3.12 · Django · Django REST Framework · drf-spectacular (Swagger)
- PostgreSQL · APScheduler (날씨·공휴일 미리 받아두기)
- 배포: Render (Docker, gunicorn)

## 폴더 구조

| 앱 | 역할 |
| --- | --- |
| `stores`, `items`, `geo` | 가게·품목 등록, 위치 → 기상청 격자 |
| `scans` | 매대 사진 인식, 위험도 판단 |
| `listings` | 할인·세트 판매, 판매 확정, 세일 현황, 행동 기록 |
| `records` | 일일 기록(만든·남은 수량), 진열 기록, 마감 기록 |
| `dashboard` | 주간 대시보드, 내일 생산 추천 |
| `home` | 홈 화면 (오늘 영업·날씨·할 일) |
| `weather` | 기상청·공휴일 조회와 캐시 |
| `uploads` | 사진 저장 (DB 저장, `/api/v1/images/{id}.jpg`로 제공) |
| `demo` | 데모 데이터 (`POST /api/v1/demo/reset`으로 초기화) |
| `common`, `config` | 공통 에러 형식, 설정 |

## 로컬 실행

```bash
python -m venv .venv
.venv\Scripts\activate        # mac/linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # 아래 값 채우기
python manage.py migrate
python manage.py runserver
```

- API 문서: http://localhost:8000/api/docs/
- 데모 데이터 넣기: `POST http://localhost:8000/api/v1/demo/reset`

| 환경 변수 | 설명 |
| --- | --- |
| `DJANGO_SECRET_KEY` | Django 비밀 키 |
| `DEBUG` | 개발 `True` / 배포 `False` |
| `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` | 허용 도메인 (쉼표로 구분) |
| `DATABASE_URL` | PostgreSQL 주소 (비우면 SQLite) |
| `DATA_GO_KR_SERVICE_KEY` | 공공데이터포털 키 (기상청·특일 정보) |
| `KAKAO_REST_API_KEY` | 카카오 로컬 API 키 |
| `GEMINI_API_KEY` | Gemini API 키 |
| `SCHEDULER_ENABLED` | `True`면 날씨(매일 20:15)·공휴일(매월 1일) 미리 받아두기 |

## API 규칙

- 모든 API 앞에 `/api/v1/`
- JSON 필드 snake_case, 날짜 `"2026-11-20"`, 시간 `"20:30"`, 시간대 `Asia/Seoul`, 금액은 원 단위 정수
- 성공: 데이터 그대로 / 에러: `{"code": "...", "message": "..."}`
- 상태 코드: 400 입력 오류 / 404 없음 / 501 준비 중 / 502 외부 API 실패
