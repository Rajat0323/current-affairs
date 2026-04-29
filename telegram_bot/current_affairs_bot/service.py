import logging
import time

from current_affairs_bot.config import Settings
from current_affairs_bot.llm_client import LLMClient
from current_affairs_bot.news_client import NewsClient
from current_affairs_bot.state_store import StateStore
from current_affairs_bot.telegram_client import TelegramClient


LOGGER = logging.getLogger(__name__)


class CurrentAffairsService:
    def __init__(
        self,
        settings: Settings,
        news_client: NewsClient,
        llm_client: LLMClient,
        telegram_client: TelegramClient,
        state_store: StateStore,
    ) -> None:
        self.settings = settings
        self.news_client = news_client
        self.llm_client = llm_client
        self.telegram_client = telegram_client
        self.state_store = state_store

    def run_cycle(self, dry_run: bool = False) -> int:
        articles = self.news_client.fetch_latest()
        fresh_articles = [article for article in articles if not self.state_store.was_posted(article)]
        selected_articles = list(reversed(fresh_articles[: self.settings.max_articles_per_cycle]))
        if not selected_articles:
            LOGGER.info("No new articles found in this cycle.")
            return 0

        posted_count = 0
        failure_count = 0
        for article in selected_articles:
            try:
                generated_post = self.llm_client.generate_post(article)
                if dry_run:
                    LOGGER.info("Dry run preview for article: %s", article.title)
                    LOGGER.info("Summary: %s", generated_post.summary)
                else:
                    self.telegram_client.broadcast(article, generated_post)
                    self.state_store.mark_posted(article)
                    LOGGER.info("Posted article to Telegram: %s", article.title)
                posted_count += 1
            except Exception:
                failure_count += 1
                LOGGER.exception("Failed to process article: %s", article.title)
        if posted_count == 0 and failure_count > 0:
            raise RuntimeError("The bot found fresh articles but failed to process all of them.")
        return posted_count

    def run_forever(self) -> None:
        LOGGER.info("Starting scheduler with %s-minute interval.", self.settings.poll_interval_minutes)
        while True:
            cycle_start = time.monotonic()
            self.run_cycle()
            elapsed = time.monotonic() - cycle_start
            sleep_seconds = max(15, self.settings.poll_interval_minutes * 60 - int(elapsed))
            LOGGER.info("Sleeping for %s seconds before next cycle.", sleep_seconds)
            time.sleep(sleep_seconds)


def build_service(settings: Settings) -> CurrentAffairsService:
    return CurrentAffairsService(
        settings=settings,
        news_client=NewsClient(settings),
        llm_client=LLMClient(settings),
        telegram_client=TelegramClient(settings),
        state_store=StateStore(settings.state_file),
    )

