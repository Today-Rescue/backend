"""APScheduler: 매일 20:15 단기예보, 매월 1일 특일 갱신"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

_scheduler = None


def job_weather():
    pass  # TODO(B): 가게들이 쓰는 (nx, ny) 목록 돌면서 update_weather


def job_holidays():
    pass  # TODO(B): 이번 달·다음 달 update_holidays


def start():
    global _scheduler
    if _scheduler:
        return
    _scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    _scheduler.add_job(job_weather, CronTrigger(hour=20, minute=15), id="weather", replace_existing=True)
    _scheduler.add_job(job_holidays, CronTrigger(day=1, hour=0, minute=10), id="holidays", replace_existing=True)
    _scheduler.start()
