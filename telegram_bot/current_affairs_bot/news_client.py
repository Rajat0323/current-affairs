import logging
from collections.abc import Callable
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

from current_affairs_bot.config import Settings
from current_affairs_bot.models import Article


LOGGER = logging.getLogger(__name__)
NEWSDATA_FREE_QUERY_CHAR_LIMIT = 100


class NewsClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def fetch_latest(self, posted_urls: set[str] | None = None) -> list[Article]:
        posted_urls = posted_urls or set()
        articles: list[Article] = []
        seen_urls: set[str] = set()
        fresh_count = 0

        for provider_name, provider_call in self._provider_plan():
            try:
                provider_items = provider_call()
            except Exception as exc:
                LOGGER.warning("Provider %s failed and will be skipped: %s", provider_name, exc)
                continue

            batch = self._filter_and_rank_articles(provider_name, provider_items)
            provider_added = 0
            provider_fresh = 0
            for article in batch:
                if article.url in seen_urls:
                    continue
                seen_urls.add(article.url)
                articles.append(article)
                provider_added += 1
                if article.url not in posted_urls:
                    fresh_count += 1
                    provider_fresh += 1

            LOGGER.info(
                "Provider %s returned %s unique article(s), including %s fresh candidate(s).",
                provider_name,
                provider_added,
                provider_fresh,
            )
            if fresh_count >= self.settings.max_articles_per_cycle:
                break

        LOGGER.info(
            "Aggregated %s unique candidate article(s) across providers with %s fresh candidate(s).",
            len(articles),
            fresh_count,
        )
        return articles

    def _filter_and_rank_articles(self, provider_name: str, items: list[Article]) -> list[Article]:
        accepted: list[tuple[int, int, Article]] = []
        rejected_count = 0
        for index, article in enumerate(items):
            score = self._article_relevance_score(article)
            if score < self.settings.minimum_article_relevance_score:
                rejected_count += 1
                LOGGER.debug(
                    "Rejected article from %s with score=%s title=%s",
                    provider_name,
                    score,
                    article.title,
                )
                continue
            accepted.append((score, -index, article))

        accepted.sort(reverse=True)
        if rejected_count:
            LOGGER.info(
                "Filtered out %s low-quality article(s) from %s based on source/topic rules.",
                rejected_count,
                provider_name,
            )
        return [article for _, _, article in accepted]

    def _article_relevance_score(self, article: Article) -> int:
        domain = self._extract_domain(article.url)
        if not domain:
            return -10

        combined_text = " ".join(
            [
                article.title,
                article.description,
                article.content,
                article.source,
            ]
        ).lower()

        if self._matches_any_domain(domain, self.settings.blocked_source_domains):
            return -10
        if any(keyword.lower() in combined_text for keyword in self.settings.blocked_topic_keywords):
            return -10
        if self._is_stale(article.published_at):
            return -10

        score = 0
        preferred_matches = sum(
            1 for keyword in self.settings.preferred_topic_keywords if keyword.lower() in combined_text
        )
        if preferred_matches == 0:
            return -10
        if self._matches_any_domain(domain, self.settings.allowed_source_domains):
            score += 3
        elif self.settings.allowed_source_domains:
            score -= 2
        if "india" in combined_text or "indian" in combined_text:
            score += 2
        score += 1
        score += min(6, preferred_matches)

        # Light penalty for ultra-short or vague titles that tend to perform poorly for exam prep.
        if len(article.title.split()) < 5:
            score -= 1
        if domain.endswith(".gov.in") or domain.endswith(".nic.in"):
            score += 2
        if "exclusive" in combined_text or "viral" in combined_text:
            score -= 2
        if "?" in article.title:
            score -= 1

        return score

    def _is_stale(self, published_at: str) -> bool:
        if not published_at or self.settings.max_article_age_hours <= 0:
            return False
        try:
            parsed = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
        return age_seconds > self.settings.max_article_age_hours * 3600

    def _extract_domain(self, url: str) -> str:
        hostname = (urlparse(url).hostname or "").lower().strip()
        if hostname.startswith("www."):
            hostname = hostname[4:]
        return hostname

    def _matches_any_domain(self, domain: str, patterns: tuple[str, ...]) -> bool:
        for pattern in patterns:
            cleaned = pattern.lower().strip()
            if not cleaned:
                continue
            if domain == cleaned or domain.endswith(f".{cleaned}"):
                return True
        return False

    def _provider_plan(self) -> list[tuple[str, Callable[[], list[Article]]]]:
        plan: list[tuple[str, Callable[[], list[Article]]]] = []

        if self.settings.newsdata_api_key:
            plan.append(
                (
                    "newsdata-india",
                    lambda: self._fetch_newsdata(
                        query=self.settings.newsdata_india_query,
                        country=self.settings.newsdata_india_country,
                    ),
                )
            )
            plan.append(
                (
                    "newsdata-world",
                    lambda: self._fetch_newsdata(
                        query=self.settings.newsdata_world_query,
                        country="",
                    ),
                )
            )

        if self.settings.news_api_key:
            plan.append(("newsapi-world", self._fetch_newsapi))

        return plan

    def _fetch_newsapi(self) -> list[Article]:
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
        return self._normalize_newsapi_articles(payload.get("articles", []))

    def _fetch_newsdata(self, query: str, country: str) -> list[Article]:
        last_error: Exception | None = None
        for params in self._newsdata_request_variants(query, country):
            response = self.session.get(
                self.settings.newsdata_api_url,
                params=params,
                timeout=self.settings.request_timeout_seconds,
            )
            payload = self._safe_json(response)

            if response.status_code == 422:
                last_error = RuntimeError(
                    "NewsData.io rejected the request parameters. "
                    f"Response: {payload}"
                )
                LOGGER.warning(
                    "NewsData.io returned HTTP 422 for params=%s. Trying a narrower fallback.",
                    self._summarize_newsdata_params(params),
                )
                continue

            if not response.ok:
                raise RuntimeError(
                    f"NewsData.io request failed with HTTP {response.status_code}. Response: {payload}"
                )

            status = str(payload.get("status", "")).lower() if isinstance(payload, dict) else ""
            if status not in {"", "ok", "success"}:
                raise RuntimeError(f"NewsData.io returned an unexpected payload: {payload}")
            return self._normalize_newsdata_articles(payload.get("results", []))

        if last_error is not None:
            raise last_error
        return []

    def _newsdata_request_variants(self, query: str, country: str) -> list[dict[str, str]]:
        variants: list[dict[str, str]] = []
        seen_keys: set[tuple[tuple[str, str], ...]] = set()
        for candidate_query in self._newsdata_query_candidates(query=query, country=country):
            params = {
                "apikey": self.settings.newsdata_api_key,
                "language": self.settings.news_language,
            }
            if country:
                params["country"] = country
            if candidate_query:
                params["q"] = candidate_query

            dedupe_key = tuple(sorted(params.items()))
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            variants.append(params)
        return variants

    def _newsdata_query_candidates(self, query: str, country: str) -> list[str]:
        normalized_query = " ".join(query.split())
        candidates: list[str] = []
        if normalized_query:
            candidates.append(normalized_query)

        fallback_terms = (
            ["India", "government", "economy", "policy", "parliament", "science"]
            if country
            else ["government", "economy", "policy", "science", "diplomacy", "environment"]
        )
        shortened_query = self._join_or_terms_with_limit(fallback_terms, NEWSDATA_FREE_QUERY_CHAR_LIMIT)
        if shortened_query:
            candidates.append(shortened_query)
        if fallback_terms:
            candidates.append(fallback_terms[0])

        # NewsData accepts requests without q, which lets us fetch top latest items
        # for the selected country/worldwide when keyword search is too restrictive.
        candidates.append("")
        return candidates

    def _join_or_terms_with_limit(self, terms: list[str], limit: int) -> str:
        joined_terms: list[str] = []
        current = ""
        for term in terms:
            stripped = term.strip()
            if not stripped:
                continue
            candidate = stripped if not current else f"{current} OR {stripped}"
            if len(candidate) > limit:
                break
            current = candidate
            joined_terms.append(stripped)
        return " OR ".join(joined_terms)

    def _safe_json(self, response: requests.Response) -> dict | list | str:
        try:
            return response.json()
        except ValueError:
            return {"raw_text": response.text}

    def _summarize_newsdata_params(self, params: dict[str, str]) -> dict[str, str]:
        summary = dict(params)
        if "apikey" in summary:
            summary["apikey"] = "***"
        return summary

    def _normalize_newsapi_articles(self, items: list[dict]) -> list[Article]:
        articles: list[Article] = []
        seen_urls: set[str] = set()
        for item in items:
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
        return articles

    def _normalize_newsdata_articles(self, items: list[dict]) -> list[Article]:
        articles: list[Article] = []
        seen_urls: set[str] = set()
        for item in items:
            url = (item.get("link") or "").strip()
            title = (item.get("title") or "").strip()
            if not url or not title or url in seen_urls:
                continue

            source_name = (item.get("source_id") or item.get("source_name") or "Unknown Source").strip()
            seen_urls.add(url)
            articles.append(
                Article(
                    title=title,
                    description=(item.get("description") or "").strip(),
                    url=url,
                    source=source_name or "Unknown Source",
                    published_at=(item.get("pubDate") or "").strip(),
                    content=(item.get("content") or item.get("description") or "").strip(),
                )
            )
        return articles
