# Today-Rescue-back

## 실행

```bash
python -m venv .venv
.venv\Scripts\activate        # mac/linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # 값 채우기
python manage.py migrate
python manage.py runserver
```

- API 문서: http://localhost:8000/api/docs/
- 모든 API 앞에 `/api/v1/`

## 담당

| 담당 | 앱 |
| --- | --- |
| 공통 | config, common |
| A | geo, stores, items, records, home, demo |
| B | scans, uploads, weather, listings, dashboard |

## 공통 규칙

- JSON 필드: snake_case
- 날짜 `"2026-11-10"`, 시간 `"20:30"`, 시간대 `Asia/Seoul`
- 금액: 원 단위 정수
- 성공 응답: 데이터 그대로 / 에러: `{"code": "...", "message": "..."}`
- 상태 코드: 400 입력 오류 / 404 없음 / 502 외부 API 실패
- 데모 가게 `id = 1`

## 가게 위치 · 날씨 격자

Grid 테이블을 따로 두지 않고 Store에 좌표를 직접 저장해요.

1. 프론트: `POST /api/v1/stores` → `{"name": "...", "lat": 37.55, "lng": 126.92}`
2. A (`stores.services.latlng_to_grid`): lat, lng → 기상청 격자 `nx, ny` 계산해서 Store에 저장
3. B (`weather.services.get_weather(nx, ny, date)`): 저장된 nx, ny로 날씨 조회

## 서로 부르는 함수 (이름·모양 고정)

| 함수 | 만든 쪽 → 호출하는 쪽 |
| --- | --- |
| `records.services.update_left_qty(store_id, date, {item_id: left_qty})` | A → B (스캔 확정) |
| `records.services.get_records(store_id, start, end)` | A → B (대시보드) |
| `weather.services.get_weather(nx, ny, date)` | B → A (홈) |
| `weather.services.is_holiday(date)` | B → A (홈) |
