import os
import sys

from django.apps import AppConfig


class WeatherConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "weather"
    verbose_name = "날씨·특일"

    def ready(self):
        if os.getenv("SCHEDULER_ENABLED", "False") != "True":
            return
        # manage.py migrate, fetch_weather 등 명령 실행 땐 켜지 않음
        if len(sys.argv) > 1 and sys.argv[1] not in ("runserver",) and "gunicorn" not in sys.argv[0]:
            return
        # runserver 자동 리로드 때 두 번 켜지는 것 방지
        if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
            return
        from . import scheduler

        scheduler.start()
