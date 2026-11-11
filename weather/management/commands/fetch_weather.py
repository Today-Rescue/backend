from django.core.management.base import BaseCommand

from weather import services


class Command(BaseCommand):
    help = "기상청 예보·특일 수동 수집"

    def add_arguments(self, parser):
        parser.add_argument("--nx", type=int, help="특정 격자만 (--ny 같이)")
        parser.add_argument("--ny", type=int)
        parser.add_argument("--skip-weather", action="store_true", help="날씨 건너뛰기")
        parser.add_argument("--skip-holidays", action="store_true", help="특일 건너뛰기")

    def handle(self, *args, **opts):
        if not opts["skip_weather"]:
            if opts["nx"] is not None and opts["ny"] is not None:
                results = {(opts["nx"], opts["ny"]): services.update_weather(opts["nx"], opts["ny"])}
            else:
                results = services.update_all_weather()
            if not results:
                self.stdout.write("좌표가 있는 가게가 없어요 (--nx --ny 로 지정 가능)")
            for (nx, ny), r in results.items():
                self.stdout.write(f"날씨 ({nx}, {ny}): {r}")

        if not opts["skip_holidays"]:
            count = services.update_upcoming_holidays()
            self.stdout.write(f"특일: {count}건")

        self.stdout.write(self.style.SUCCESS("완료"))
