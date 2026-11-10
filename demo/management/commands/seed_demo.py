from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "데모 가게(id=1)·품목·4주치 기록 생성"

    def handle(self, *args, **options):
        from django.core.management import call_command
        from django.db import transaction

        from stores.models import Store

        with transaction.atomic():
            Store.objects.filter(is_demo=True).delete()
            # TODO(A): demo_store.json 채운 뒤 사용 (가게 id=1 고정)
            call_command("loaddata", "demo_store")
        self.stdout.write(self.style.SUCCESS("데모 데이터 초기화 완료"))
