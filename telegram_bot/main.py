"""
main.py — Entry point for the UPSC Current Affairs Telegram Bot.

Usage:
    python main.py             # Start the scheduler (runs indefinitely)
    python main.py --test      # Send a test message and exit
    python main.py --now       # Run all three jobs immediately and exit
    python main.py --morning   # Run only the morning job now
    python main.py --afternoon # Run only the afternoon quiz now
    python main.py --evening   # Run only the evening revision now
"""

import asyncio
import argparse
import logging
import signal
import sys
from datetime import datetime

import pytz

import config
from scheduler import create_scheduler, print_next_runs
from bot import send_message, send_test_message
from scheduler import job_morning_current_affairs, job_afternoon_quiz, job_evening_revision

# ──────────────────────────────────────────────
# Logging setup
# ──────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("upsc_bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# CLI argument parsing
# ──────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="UPSC Current Affairs Telegram Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py               # Start scheduler (runs 24/7)
  python main.py --test        # Send a test ping to the channel
  python main.py --now         # Fire all three jobs immediately
  python main.py --morning     # Send morning current affairs now
  python main.py --afternoon   # Send afternoon MCQ quiz now
  python main.py --evening     # Send evening revision now
        """,
    )
    parser.add_argument("--test", action="store_true", help="Send a test message and exit")
    parser.add_argument("--now", action="store_true", help="Run all jobs immediately and exit")
    parser.add_argument("--morning", action="store_true", help="Run morning job now and exit")
    parser.add_argument("--afternoon", action="store_true", help="Run afternoon quiz now and exit")
    parser.add_argument("--evening", action="store_true", help="Run evening revision now and exit")
    return parser.parse_args()


# ──────────────────────────────────────────────
# Main async runner
# ──────────────────────────────────────────────

async def run_scheduled():
    """Start the APScheduler and keep the bot running indefinitely."""
    scheduler = create_scheduler()
    scheduler.start()

    IST = pytz.timezone("Asia/Kolkata")
    start_time = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    logger.info("UPSC Bot scheduler started at %s IST", start_time)
    print_next_runs(scheduler)

    # Graceful shutdown on SIGINT / SIGTERM
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def _shutdown(sig):
        logger.info("Received signal %s — shutting down scheduler gracefully...", sig.name)
        scheduler.shutdown(wait=False)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown, sig)

    print("=" * 55)
    print("  UPSC Current Affairs Bot is running.")
    print(f"  Started: {start_time} IST")
    print("  Schedule:")
    print(f"    🌅 Morning   — {config.MORNING_HOUR:02d}:{config.MORNING_MINUTE:02d} IST")
    print(f"    📝 Afternoon — {config.AFTERNOON_HOUR:02d}:{config.AFTERNOON_MINUTE:02d} IST")
    print(f"    🌙 Evening   — {config.EVENING_HOUR:02d}:{config.EVENING_MINUTE:02d} IST")
    print("  Press Ctrl+C to stop.")
    print("=" * 55)

    await stop_event.wait()
    logger.info("Bot shut down cleanly.")


async def run_test():
    logger.info("Sending test message...")
    ok = await send_test_message()
    if ok:
        print("✅ Test message sent successfully! Check your Telegram channel.")
    else:
        print("❌ Failed to send test message. Check your credentials and logs.")


async def run_now():
    logger.info("Running all three jobs immediately...")
    await job_morning_current_affairs()
    await job_afternoon_quiz()
    await job_evening_revision()
    print("✅ All three jobs ran. Check your Telegram channel.")


# ──────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────

def main():
    # Validate environment before doing anything
    try:
        config.validate_config()
    except EnvironmentError as e:
        print(f"\n❌ Configuration Error:\n{e}\n")
        sys.exit(1)

    args = parse_args()

    if args.test:
        asyncio.run(run_test())
    elif args.now:
        asyncio.run(run_now())
    elif args.morning:
        asyncio.run(job_morning_current_affairs())
        print("✅ Morning job complete.")
    elif args.afternoon:
        asyncio.run(job_afternoon_quiz())
        print("✅ Afternoon quiz job complete.")
    elif args.evening:
        asyncio.run(job_evening_revision())
        print("✅ Evening revision job complete.")
    else:
        asyncio.run(run_scheduled())


if __name__ == "__main__":
    main()
