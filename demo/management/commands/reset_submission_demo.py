from collections import defaultdict
from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from dashboard.recommend import WEEKDAYS, WEEKS, weekday_avg_sold
from items.models import Item
from listings.models import ActionLog, CampaignItem, SaleCampaign, SalesEvent
from listings.services import sale_price
from records.models import CloseRecord, DailyProduction, DailyRecord
from stores.models import Store

STORE_ID = 1
ITEM_IDS = tuple(range(8, 15))
RATE = 30


def at(day, hour):
    return timezone.make_aware(datetime.combine(day, time(hour)))


class Command(BaseCommand):
    help = "한빛베이커리 최종 제출용 기록을 미리 보거나 지정 범위의 테스트 기록을 교체합니다."

    def add_arguments(self, parser):
        parser.add_argument("--as-of", type=date.fromisoformat, help="시연 영업일 (기본값: 오늘)")
        parser.add_argument(
            "--apply-confirmed-test-data",
            action="store_true",
            help="미리 보기 범위의 대상 행이 모두 테스트 기록임을 확인한 후 적용",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["apply_confirmed_test_data"] and options["as_of"] is None:
            raise CommandError("적용하려면 미리 보기에 사용한 --as-of 날짜를 지정해 주세요.")
        today = timezone.localdate()
        anchor = options["as_of"] or today
        if anchor > today:
            raise CommandError("시연 영업일은 오늘 이후일 수 없습니다.")

        store = Store.objects.select_for_update().filter(pk=STORE_ID).first()
        if not store or store.name != "한빛베이커리" or not store.is_demo:
            raise CommandError("매장 1이 한빛베이커리 데모 매장인지 확인해 주세요.")
        items = list(Item.objects.filter(store=store, pk__in=ITEM_IDS, is_active=True).order_by("pk"))
        if tuple(item.pk for item in items) != ITEM_IDS:
            raise CommandError("매장 1에 활성 품목 ID 8~14가 모두 있어야 합니다.")
        if WEEKDAYS[anchor.weekday()] in store.closed_days:
            raise CommandError("시연일은 매장의 영업일로 지정해 주세요.")

        first = anchor - timedelta(weeks=WEEKS)
        scope = dict(store=store, item_id__in=ITEM_IDS, date__range=(first, anchor))
        daily = DailyRecord.objects.filter(**scope)
        production = DailyProduction.objects.filter(**scope)
        closing = CloseRecord.objects.filter(**scope)
        campaigns = self.campaigns_to_replace(store, first, anchor)
        campaign_ids = [campaign.pk for campaign in campaigns]
        sale_events = SalesEvent.objects.filter(campaign_id__in=campaign_ids)
        closing_dates = set(closing.values_list("date", flat=True))
        mixed_closing_dates = CloseRecord.objects.filter(
            store=store, date__in=closing_dates,
        ).exclude(item_id__in=ITEM_IDS).values_list("date", flat=True)
        close_logs = ActionLog.objects.filter(
            store=store, date__in=closing_dates, type=ActionLog.Type.CLOSE,
        ).exclude(date__in=mixed_closing_dates)
        campaign_logs = ActionLog.objects.filter(
            store=store, date__range=(first, anchor),
            type__in=(
                ActionLog.Type.SALE_START, ActionLog.Type.BUNDLE_START,
                ActionLog.Type.SALE_UPDATE, ActionLog.Type.SALE_STOP,
            ),
            detail__campaign_id__in=campaign_ids,
        )
        plans = self.plan(store, items, first, anchor)
        self.stdout.write(
            f"매장 {STORE_ID}, 품목 8~14, {first} ~ {anchor}\n"
            f"교체 대상: 일일 {daily.count()}, 생산 {production.count()}, "
            f"마감 {closing.count()}, 캠페인 {len(campaign_ids)}, 판매 {sale_events.count()}, "
            f"관련 로그 {close_logs.count() + campaign_logs.count()}\n"
            f"생성 예정: 영업일 {len(plans)}일, 일일·생산 각 {len(plans) * len(items)}행, "
            f"마감·판매 각 {(len(plans) - 1) * len(items)}행"
        )
        if not options["apply_confirmed_test_data"]:
            self.stdout.write("미리 보기 완료. 적용하려면 --apply-confirmed-test-data를 지정하세요.")
            return

        close_logs.delete()
        campaign_logs.delete()
        SaleCampaign.objects.filter(pk__in=campaign_ids).delete()
        for queryset in (closing, production, daily):
            queryset.delete()
        expected = self.write_records(store, plans, anchor)
        self.verify(store, first, anchor, expected)
        self.stdout.write(self.style.SUCCESS("재설정 및 수량 검증 완료"))

    def campaigns_to_replace(self, store, first, anchor):
        campaigns = SaleCampaign.objects.filter(
            store=store, started_at__date__range=(first, anchor),
        ).prefetch_related("items", "sales", "bundle__items")
        result = []
        for campaign in campaigns:
            bundle = getattr(campaign, "bundle", None)
            item_ids = {row.item_id for row in campaign.items.all()}
            item_ids.update(row.item_id for row in campaign.sales.all() if row.item_id is not None)
            if bundle is not None:
                item_ids.update(row.item_id for row in bundle.items.all())
            if item_ids.intersection(ITEM_IDS):
                if not item_ids.issubset(ITEM_IDS):
                    raise CommandError(f"캠페인 {campaign.pk}에 범위 밖 품목이 함께 있어 중단합니다.")
                result.append(campaign)
        return result

    def plan(self, store, items, first, anchor):
        plans = {}
        for offset in range((anchor - first).days + 1):
            day = first + timedelta(days=offset)
            if WEEKDAYS[day.weekday()] in store.closed_days:
                continue
            rows = []
            for index, item in enumerate(items):
                made = 32 - index * 3 + day.weekday() + offset // 7
                sale_stock = 4 + (offset + index) % 4
                discounted = 2 + (offset + index) % 3
                rows.append((item, made, sale_stock, discounted))
            plans[day] = rows
        return plans

    def write_records(self, store, plans, anchor):
        expected = {}
        for day, rows in plans.items():
            campaign = None
            if day < anchor:
                campaign = SaleCampaign.objects.create(
                    store=store, type=SaleCampaign.Type.DISCOUNT, status=SaleCampaign.Status.ENDED,
                    discount_rate=RATE, started_at=at(day, 18), ends_at=at(day, 20),
                    stopped_at=at(day, 20),
                )
            for item, made, sale_stock, discounted in rows:
                left = sale_stock - discounted if campaign else None
                DailyRecord.objects.create(
                    store=store, item=item, date=day, made_qty=made,
                    left_qty=left, sold_out=left == 0,
                )
                DailyProduction.objects.create(
                    store=store, item=item, date=day, qty=made,
                    source=DailyProduction.Source.INITIAL, recorded_at=at(day, 8),
                )
                if campaign:
                    price = sale_price(item.price, RATE)
                    CampaignItem.objects.create(
                        campaign=campaign, item=item, start_qty=sale_stock, sale_price=price,
                    )
                    sale = SalesEvent.objects.create(
                        campaign=campaign, item=item, quantity=discounted, unit_price=price,
                        channel=SalesEvent.Channel.STORE,
                    )
                    SalesEvent.objects.filter(pk=sale.pk).update(sold_at=at(day, 19))
                    CloseRecord.objects.create(
                        store=store, item=item, date=day, left_qty=left,
                        disposed_qty=left, carryover_qty=0, closed_at=at(day, 20),
                    )
                expected[day, item.pk] = (made, sale_stock, discounted, left)
        return expected

    def verify(self, store, first, anchor, expected):
        scope = dict(store=store, item_id__in=ITEM_IDS, date__range=(first, anchor))
        daily = {(r.date, r.item_id): r for r in DailyRecord.objects.filter(**scope)}
        production = {
            (row["date"], row["item_id"]): row["total"]
            for row in DailyProduction.objects.filter(**scope).values("date", "item_id").annotate(total=Sum("qty"))
        }
        closing = {(r.date, r.item_id): r for r in CloseRecord.objects.filter(**scope)}
        campaign_scope = dict(
            campaign__store=store, campaign__started_at__date__range=(first, anchor), item_id__in=ITEM_IDS,
        )
        sold = defaultdict(int)
        for event in SalesEvent.objects.filter(**campaign_scope).select_related("campaign"):
            sold[timezone.localdate(event.campaign.started_at), event.item_id] += event.quantity
        stock = {
            (timezone.localdate(row.campaign.started_at), row.item_id): row.start_qty
            for row in CampaignItem.objects.filter(**campaign_scope).select_related("campaign")
        }
        history_keys = {key for key in expected if key[0] < anchor}
        if (daily.keys() != expected.keys() or production.keys() != expected.keys()
                or closing.keys() != history_keys or sold.keys() != history_keys or stock.keys() != history_keys):
            raise CommandError("생성된 일일·생산·판매·마감 기록 범위가 일치하지 않습니다.")
        for key, (made, sale_stock, discounted, left) in expected.items():
            record = daily[key]
            if record.made_qty != made or production[key] != made or record.left_qty != left:
                raise CommandError(f"{key} 생산·잔여 수량 불일치")
            if record.sold_out != (left == 0):
                raise CommandError(f"{key} 품절 상태 불일치")
            if key in history_keys:
                close = closing[key]
                regular_sold = made - stock[key]
                if (
                    stock[key] != sale_stock or sold[key] != discounted
                    or min(regular_sold, sold[key], left, close.disposed_qty, close.carryover_qty) < 0
                    or made != regular_sold + sold[key] + left
                    or left != close.left_qty or left != close.disposed_qty + close.carryover_qty
                    or close.carryover_qty != 0
                ):
                    raise CommandError(f"{key} 판매·폐기·이월 수량 불일치")

        same_weekdays = [anchor - timedelta(weeks=week) for week in range(1, WEEKS + 1)]
        target_averages = {
            item_id: sum(production[day, item_id] - closing[day, item_id].left_qty for day in same_weekdays) / WEEKS
            for item_id in ITEM_IDS
        }
        actual_averages = weekday_avg_sold(store.pk, anchor)
        if any(actual_averages.get(item_id) != value for item_id, value in target_averages.items()):
            raise CommandError("추천용 최근 4주 같은 요일 판매 평균 불일치")
