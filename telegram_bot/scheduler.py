"""
scheduler.py — APScheduler setup for morning, afternoon, and evening jobs.

Schedule (IST):
  07:00  Morning  — Daily Current Affairs Summary
  13:00  Afternoon — MCQ Quiz
  19:00  Evening  — Revision Points
"""

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

import config
from news_fetcher import fetch_upsc_articles
from formatter import format_morning_summary, format_mcq_quiz, format_evening_revision
from bot import send_message

logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")


# ──────────────────────────────────────────────
# Job functions
# ──────────────────────────────────────────────

async def job_morning_current_affairs():
    """Fetch today's news and send the morning current affairs digest."""
    logger.info("Running morning current affairs job...")
    date_str = datetime.now(IST).strftime("%A, %d %B %Y")

    try:
        articles = fetch_upsc_articles(max_articles=config.NEWS_API_MAX_ARTICLES)
        if not articles:
            await send_message(
                "⚠️ <b>Morning Update</b>\nCould not fetch current affairs today. "
                "Please check back later."
            )
            return

        message = format_morning_summary(articles, date_str)
        success = await send_message(message)
        if success:
            logger.info("Morning current affairs sent successfully (%d articles)", len(articles))
        else:
            logger.error("Failed to send morning current affairs")

    except Exception as e:
        logger.error("Error in morning job: %s", e, exc_info=True)


async def job_afternoon_quiz():
    """Send the afternoon MCQ quiz based on today's news."""
    logger.info("Running afternoon MCQ quiz job...")
    date_str = datetime.now(IST).strftime("%A, %d %B %Y")

    try:
        articles = fetch_upsc_articles(max_articles=config.NEWS_API_MAX_ARTICLES)
        if not articles:
            await send_message(
                "⚠️ <b>Afternoon Quiz</b>\nCould not generate quiz today. "
                "Please check back later."
            )
            return

        message = format_mcq_quiz(articles, date_str)
        success = await send_message(message)
        if success:
            logger.info("Afternoon MCQ quiz sent successfully")
        else:
            logger.error("Failed to send afternoon MCQ quiz")

    except Exception as e:
        logger.error("Error in afternoon quiz job: %s", e, exc_info=True)


async def job_evening_revision():
    """Send the evening revision recap."""
    logger.info("Running evening revision job...")
    date_str = datetime.now(IST).strftime("%A, %d %B %Y")

    try:
        articles = fetch_upsc_articles(max_articles=config.NEWS_API_MAX_ARTICLES)
        if not articles:
            await send_message(
                "⚠️ <b>Evening Revision</b>\nCould not load articles for revision today."
            )
            return

        message = format_evening_revision(articles, date_str)
        success = await send_message(message)
        if success:
            logger.info("Evening revision sent successfully")
        else:
            logger.error("Failed to send evening revision")

    except Exception as e:
        logger.error("Error in evening revision job: %s", e, exc_info=True)


# ──────────────────────────────────────────────
# Scheduler setup
# ──────────────────────────────────────────────

def create_scheduler() -> AsyncIOScheduler:
    """
    Create and configure the APScheduler with all three daily jobs.

    All times are in IST (Asia/Kolkata).
    """
    scheduler = AsyncIOScheduler(timezone=IST)

    # Morning: 7:00 AM IST
    scheduler.add_job(
        job_morning_current_affairs,
        trigger=CronTrigger(
            hour=config.MORNING_HOUR,
            minute=config.MORNING_MINUTE,
            timezone=IST,
        ),
        id="morning_current_affairs",
        name="Morning Current Affairs Digest",
        replace_existing=True,
        misfire_grace_time=300,   # Allow 5-minute grace if job misses its time
    )

    # Afternoon: 1:00 PM IST
    scheduler.add_job(
        job_afternoon_quiz,
        trigger=CronTrigger(
            hour=config.AFTERNOON_HOUR,
            minute=config.AFTERNOON_MINUTE,
            timezone=IST,
        ),
        id="afternoon_mcq_quiz",
        name="Afternoon MCQ Quiz",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Evening: 7:00 PM IST
    scheduler.add_job(
        job_evening_revision,
        trigger=CronTrigger(
            hour=config.EVENING_HOUR,
            minute=config.EVENING_MINUTE,
            timezone=IST,
        ),
        id="evening_revision",
        name="Evening Revision",
        replace_existing=True,
        misfire_grace_time=300,
    )

    logger.info(
        "Scheduler configured — Morning %02d:%02d | Afternoon %02d:%02d | Evening %02d:%02d IST",
        config.MORNING_HOUR, config.MORNING_MINUTE,
        config.AFTERNOON_HOUR, config.AFTERNOON_MINUTE,
        config.EVENING_HOUR, config.EVENING_MINUTE,
    )

    return scheduler


def print_next_runs(scheduler: AsyncIOScheduler):
    """Log the next scheduled run time for each job."""
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        if next_run:
            logger.info(
                "Next run of '%s': %s IST",
                job.name,
                next_run.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
            )
