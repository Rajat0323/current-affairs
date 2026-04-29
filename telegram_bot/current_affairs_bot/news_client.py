import logging

import requests

from current_affairs_bot.config import Settings
from current_affairs_bot.models import Article


LOGGER = logging.getLogger(__name__)


class NewsClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def fetch_latest(self) -> list[Article]:
        params = {
            "q": self.settings.current_affairs_query,
            "language": self.settings.news_language,
            "sortBy": "publishedAt",
            "pageSize": self.settings.news_page_size,
            "apiKey": self.settings.news_api_key,
        }
        response = self.session.get(
            self.settings.news_api_url,
            params=params,
            timeout=self.settings.request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") not in {None, "ok"}:
            raise RuntimeError(f"News API returned an unexpected payload: {payload}")

        articles: list[Article] = []
        seen_urls: set[str] = set()
        for item in payload.get("articles", []):
            url = (item.get("url") or "").strip()
            title = (item.get("title") or "").strip()
            if not url or not title or url in seen_urls:
                continue

            source_name = (
                item.get("source", {}).get("name", "Unknown Source")
                if isinstance(item.get("source"), dict)
                else "Unknown Source"
            )
            seen_urls.add(url)
            articles.append(
                Article(
                    title=title,
                    description=(item.get("description") or "").strip(),
                    url=url,
                    source=source_name.strip() or "Unknown Source",
                    published_at=(item.get("publishedAt") or "").strip(),
                    content=(item.get("content") or item.get("description") or "").strip(),
                )
            )

        LOGGER.info("Fetched %s candidate articles from the news API.", len(articles))
        return articles

