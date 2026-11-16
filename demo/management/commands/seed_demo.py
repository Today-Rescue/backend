"""데모 데이터 생성: 한빛베이커리(id=1) + 품목 7개 + 4주치 기록 + 마감 세일 + 날씨

python manage.py seed_demo  (POST /demo/reset 도 같은 명령을 실행해요)
"""
import random
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.core.management.color import no_style
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

DEMO_STORE_ID = 1
DEMO_DAYS = 28
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WEEKDAY_FACTOR = [1.0, 0.9, 0.9, 1.0, 1.1, 1.35, 1.25]  # 월~일 판매량 보정

# 이름, 정가, 원가, 유통기한, 하루 기본 생산량
ITEMS = [
    ("소금빵", 3500, 1200, "today", 40),
    ("크루아상", 4000, 1500, "today", 30),
    ("앙버터", 5000, 1900, "today", 20),
    ("소보로빵", 2800, 900, "today", 25),
    ("식빵", 5500, 2000, "day1", 12),
    ("바게트", 4500, 1500, "day1", 15),
    ("올리브 치아바타", 4800, 1700, "day2", 10),
]

# 남은 빵 중 내일 판매로 넘기는 비율 (나머지는 폐기)
CARRYOVER_RATE = {"today": 0.0, "day1": 0.5, "day2": 0.6}

# 오늘부터 5일치 날씨: 최고, 최저, 강수확률, 비 여부
WEATHER = [(14, 5, 10, False), (12, 3, 30, False), (10, 2, 60, True), (9, 1, 20, False), (11, 2, 0, False)]


def split_qty(total, parts, rng):
    """total개를 parts건으로 나눠요 (각 건 1개 이상)"""
    parts = max(1, min(parts, total))
    cuts = sorted(rng.sample(range(1, total), parts - 1)) if parts > 1 else []
    points = [0] + cuts + [total]
    return [points[i + 1] - points[i] for i in range(parts)]


class Command(BaseCommand):
    help = "데모 가게(id=1)·품목·4주치 기록·마감 세일·날씨 생성"

    def handle(self, *args, **options):
        from items.models import Item
        from listings.models import CampaignItem, SaleCampaign, SalesEvent
        from records.models import CloseRecord, DailyProduction, DailyRecord
        from stores.models import Store
        from weather.models import WeatherDaily

        rng = random.Random(42)  # 항상 같은 데이터가 나오도록 고정
        today = timezone.localdate()

        def at(day, hour, minute=0):
            return timezone.make_aware(datetime.combine(day, time(hour, minute)))

        with transaction.atomic():
            # 데모 가게는 id=1 고정이라 기존 id=1(테스트용 포함)도 함께 지워요
            Store.objects.filter(Q(is_demo=True) | Q(pk=DEMO_STORE_ID)).delete()
            store = Store.objects.create(
                pk=DEMO_STORE_ID,
                name="한빛베이커리",
                lat=37.5563,
                lng=126.9236,
                nx=59,
                ny=126,
                is_demo=True,
                dong="서교동",
                open_time=time(8, 0),
                close_time=time(21, 0),
                closed_days=["mon"],
                alert_hours_before=2,
            )

            items = []
            for name, price, cost, shelf_life, base in ITEMS:
                item = Item.objects.create(
                    store=store, name=name, price=price, cost=cost, shelf_life=shelf_life
                )
                items.append((item, base))

            # 지난 4주: 마감까지 끝난 기록
            for offset in range(DEMO_DAYS, 0, -1):
                day = today - timedelta(days=offset)
                if WEEKDAYS[day.weekday()] in store.closed_days:
                    continue
                factor = WEEKDAY_FACTOR[day.weekday()]

                has_campaign = rng.random() < 0.6
                rows = []
                for item, base in items:
                    made = max(6, round(base * factor * rng.uniform(0.9, 1.1)))
                    extra = round(made * 0.2) if rng.random() < 0.12 else 0
                    scan_left = 0 if rng.random() < 0.12 else round(made * rng.uniform(0.08, 0.30))
                    sold = round(scan_left * rng.uniform(0.4, 0.8)) if has_campaign else 0
                    rows.append(
                        {"item": item, "made": made, "extra": extra, "scan_left": scan_left, "sold": sold}
                    )

                for r in rows:
                    item = r["item"]
                    left = r["scan_left"] - r["sold"]  # 남은 수량 = 스캔 확정값 - 판매
                    DailyRecord.objects.create(
                        store=store, item=item, date=day,
                        made_qty=r["made"], left_qty=left, sold_out=(left == 0),
                    )
                    DailyProduction.objects.create(
                        store=store, item=item, date=day, qty=r["made"] - r["extra"],
                        source="initial", recorded_at=at(day, 7, 30),
                    )
                    if r["extra"] > 0:
                        DailyProduction.objects.create(
                            store=store, item=item, date=day, qty=r["extra"],
                            source="extra", recorded_at=at(day, 13, 0),
                        )
                    carryover = round(left * CARRYOVER_RATE[item.shelf_life])
                    CloseRecord.objects.create(
                        store=store, item=item, date=day, left_qty=left,
                        disposed_qty=left - carryover, carryover_qty=carryover,
                        closed_at=at(day, 21, 5),
                    )

                sale_rows = [r for r in rows if r["sold"] > 0]
                if sale_rows:
                    campaign = SaleCampaign.objects.create(
                        store=store, type=SaleCampaign.Type.DISCOUNT,
                        status=SaleCampaign.Status.ENDED, discount_rate=30,
                        started_at=at(day, 19, 0), ends_at=at(day, 21, 0), stopped_at=at(day, 21, 0),
                    )
                    for r in sale_rows:
                        sale_price = int(r["item"].price * 0.7) // 10 * 10
                        CampaignItem.objects.create(
                            campaign=campaign, item=r["item"], sale_price=sale_price,
                            start_qty=r["scan_left"],
                        )
                        for qty in split_qty(r["sold"], rng.choice([1, 2, 3]), rng):
                            event = SalesEvent.objects.create(
                                campaign=campaign, item=r["item"], quantity=qty, unit_price=sale_price,
                                channel=rng.choices(["app", "store"], weights=[7, 3])[0],
                            )
                            SalesEvent.objects.filter(pk=event.pk).update(
                                sold_at=at(day, 19 + rng.randint(0, 1), rng.randint(0, 59))
                            )

            # 오늘: 아침에 만든 수량만 입력된 상태 (마감 전)
            if WEEKDAYS[today.weekday()] not in store.closed_days:
                factor = WEEKDAY_FACTOR[today.weekday()]
                for item, base in items:
                    made = max(6, round(base * factor))
                    DailyRecord.objects.create(
                        store=store, item=item, date=today, made_qty=made, left_qty=None, sold_out=False,
                    )
                    DailyProduction.objects.create(
                        store=store, item=item, date=today, qty=made,
                        source="initial", recorded_at=at(today, 7, 30),
                    )

            # 날씨 (스케줄러가 꺼져 있어도 추천·위험도가 동작하도록)
            for i, (tmax, tmin, pop, rain) in enumerate(WEATHER):
                WeatherDaily.objects.update_or_create(
                    nx=59, ny=126, date=today + timedelta(days=i),
                    defaults=dict(
                        tmax=tmax, tmin=tmin, pop_max=pop, has_rain=rain,
                        base_date=today.strftime("%Y%m%d"), base_time="2000",
                    ),
                )

            # id를 직접 지정했으니 PostgreSQL 번호표(시퀀스)를 맞춰요 (SQLite는 해당 없음)
            with connection.cursor() as cursor:
                for sql in connection.ops.sequence_reset_sql(no_style(), [Store]):
                    cursor.execute(sql)

        self.stdout.write(self.style.SUCCESS("데모 데이터 초기화 완료"))