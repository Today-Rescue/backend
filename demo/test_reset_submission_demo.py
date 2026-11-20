from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from dashboard.recommend import weekday_avg_sold
from demo.management.commands.reset_submission_demo import at
from items.models import Item
from listings.models import CampaignItem, SaleCampaign, SalesEvent
from records.models import CloseRecord, DailyProduction, DailyRecord
from stores.models import Store


class ResetSubmissionDemoTests(TestCase):
    anchor = date(2026, 11, 20)

    def setUp(self):
        self.store = Store.objects.create(pk=1, name="한빛베이커리", is_demo=True, closed_days=["mon"])
        for item_id in range(8, 15):
            Item.objects.create(pk=item_id, store=self.store, name=f"빵 {item_id}", price=3000)
        self.extra = Item.objects.create(pk=15, store=self.store, name="별도 품목", price=3000)
        self.test_record = DailyRecord.objects.create(
            store=self.store, item_id=8, date=self.anchor, made_qty=90,
        )

    def reset(self, *, apply=False):
        with patch.object(timezone, "now", return_value=at(self.anchor, 12)):
            call_command(
                "reset_submission_demo", as_of=self.anchor, apply_confirmed_test_data=apply, stdout=StringIO(),
            )

    def test_preview_preserves_records(self):
        self.reset()
        self.test_record.refresh_from_db()
        self.assertEqual(self.test_record.made_qty, 90)
        self.assertFalse(DailyProduction.objects.exists())

    def test_replaces_test_slice_and_seeds_four_same_weekdays(self):
        other = Store.objects.create(name="다른 매장", is_demo=True)
        other_item = Item.objects.create(store=other, name="다른 빵", price=3000)
        preserved = [
            DailyRecord.objects.create(store=other, item=other_item, date=self.anchor, made_qty=50),
            DailyRecord.objects.create(store=self.store, item=self.extra, date=self.anchor, made_qty=50),
            DailyRecord.objects.create(
                store=self.store, item_id=8, date=self.anchor - timedelta(days=29), made_qty=50,
            ),
        ]
        test_campaign = SaleCampaign.objects.create(
            store=self.store, type="discount", started_at=at(self.anchor, 18),
        )
        CampaignItem.objects.create(campaign=test_campaign, item_id=8, sale_price=2100, start_qty=5)
        self.reset(apply=True)
        counts = tuple(model.objects.count() for model in (DailyRecord, DailyProduction, CloseRecord, SalesEvent))
        self.reset(apply=True)
        self.assertEqual(
            tuple(model.objects.count() for model in (DailyRecord, DailyProduction, CloseRecord, SalesEvent)), counts,
        )
        self.assertFalse(DailyRecord.objects.filter(pk=self.test_record.pk).exists())
        self.assertFalse(SaleCampaign.objects.filter(pk=test_campaign.pk).exists())
        self.assertEqual(DailyRecord.objects.filter(pk__in=[row.pk for row in preserved]).count(), 3)
        self.assertEqual(Item.objects.filter(store=self.store, pk__range=(8, 14)).count(), 7)
        self.store.refresh_from_db()
        self.assertEqual(self.store.closed_days, ["mon"])

        for item_id in range(8, 15):
            days = [self.anchor - timedelta(weeks=week) for week in range(1, 5)]
            records = DailyRecord.objects.filter(store=self.store, item_id=item_id, date__in=days)
            self.assertEqual(records.count(), 4)
            self.assertEqual(
                weekday_avg_sold(self.store.pk, self.anchor)[item_id],
                sum(row.made_qty - row.left_qty for row in records) / 4,
            )

    def test_mixed_campaign_stops_before_deleting_any_records(self):
        mixed = SaleCampaign.objects.create(store=self.store, type="discount", started_at=at(self.anchor, 18))
        for item_id in (8, self.extra.pk):
            CampaignItem.objects.create(campaign=mixed, item_id=item_id, sale_price=2100, start_qty=5)
        with self.assertRaisesMessage(CommandError, "범위 밖 품목"):
            self.reset(apply=True)
        self.test_record.refresh_from_db()
        self.assertEqual(mixed.items.count(), 2)

    def test_verification_failure_rolls_back_deletion_and_inserts(self):
        with patch(
            "demo.management.commands.reset_submission_demo.weekday_avg_sold", return_value={},
        ), self.assertRaisesMessage(CommandError, "판매 평균 불일치"):
            self.reset(apply=True)
        self.test_record.refresh_from_db()
        self.assertEqual(self.test_record.made_qty, 90)
        self.assertFalse(DailyProduction.objects.exists())
        self.assertFalse(SaleCampaign.objects.exists())
