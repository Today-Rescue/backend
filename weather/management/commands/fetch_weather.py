from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "기상청 예보·특일 수동 수집"

    def handle(self, *args, **options):
        # TODO
        pass
