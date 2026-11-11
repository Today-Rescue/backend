"""APScheduler: 매일 20:15 단기예보, 매월 1일 특일 갱신

.env 에서 SCHEDULER_ENABLED=True 일 때만 켜짐 (weather/apps.py)
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
_scheduler = None


def job_weather():
    from .services import update_all_weather

    results = update_all_weather()
    logger.info("weather updated: %s", results)


def job_holidays():
    from .services import update_upcoming_holidays

    try:
        count = update_upcoming_holidays()
        logger.info("holidays updated: %s", count)
    except Exception:
        logger.exception("holidays update failed")


def start():
    global _scheduler
    if _scheduler:
        return
    _scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    # 20:00 발표분이 20:10쯤 올라옴 → 20:15에 수집 (다음날 최고·최저 포함)
    _scheduler.add_job(job_weather, CronTrigger(hour=20, minute=15), id="weather",
                       replace_existing=True, misfire_grace_time=600)
    _scheduler.add_job(job_holidays, CronTrigger(day=1, hour=0, minute=10), id="holidays",
                       replace_existing=True, misfire_grace_time=3600)
    _scheduler.start()
    logger.info("weather scheduler started")
