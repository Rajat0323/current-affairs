import unittest
from types import SimpleNamespace

from current_affairs_bot.models import Article
from current_affairs_bot.news_client import NewsClient


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | list) -> None:
        self.status_code = status_code
        self._payload = payload
        self.ok = 200 <= status_code < 300
        self.text = str(payload)

    def json(self) -> dict | list:
        return self._payload


class FakeGetSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, params: dict[str, str], timeout: int) -> FakeResponse:
        self.calls.append({"url": url, "params": dict(params), "timeout": timeout})
        if not self.responses:
            raise AssertionError("No fake responses remaining for NewsData request.")
        return self.responses.pop(0)


def build_settings(**overrides: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "newsdata_api_key": "pub_test_key",
        "newsdata_api_url": "https://newsdata.io/api/1/latest",
        "request_timeout_seconds": 10,
        "news_language": "en",
        "allowed_source_domains": (),
        "blocked_source_domains": (),
        "blocked_topic_keywords": (),
        "preferred_topic_keywords": ("government", "economy", "policy"),
        "minimum_article_relevance_score": 0,
        "max_article_age_hours": 0,
        "max_articles_per_cycle": 2,
        "news_api_key": "",
        "news_api_url": "https://newsapi.org/v2/everything",
        "current_affairs_query": "government OR economy",
        "newsdata_india_query": "India OR government OR economy OR policy OR science",
        "newsdata_world_query": "government OR economy OR diplomacy OR science OR policy",
        "newsdata_india_country": "in",
        "news_page_size": 10,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def build_article(url: str = "https://example.com/article") -> Article:
    return Article(
        title="Government approves new policy framework",
        description="Policy and economy update",
        url=url,
        source="Example News",
        published_at="2026-05-10T10:00:00Z",
        content="Government policy economy update for India.",
    )


class NewsClientFallbackTests(unittest.TestCase):
    def test_fetch_latest_skips_failed_provider_and_uses_next_provider(self) -> None:
        client = NewsClient(build_settings())
        article = build_article()
        client._provider_plan = lambda: [  # type: ignore[method-assign]
            ("newsdata-india", lambda: (_ for _ in ()).throw(RuntimeError("422 error"))),
            ("newsapi-world", lambda: [article]),
        ]
        client._filter_and_rank_articles = lambda provider_name, items: items  # type: ignore[method-assign]

        results = client.fetch_latest(posted_urls=set())

        self.assertEqual(results, [article])

    def test_fetch_newsdata_retries_with_shorter_query_after_422(self) -> None:
        client = NewsClient(build_settings())
        client.session = FakeGetSession(
            [
                FakeResponse(422, {"status": "error", "results": [], "message": "query too long"}),
                FakeResponse(
                    200,
                    {
                        "status": "success",
                        "results": [
                            {
                                "title": "Government approves new policy framework",
                                "link": "https://example.com/article",
                                "source_id": "example-news",
                                "pubDate": "2026-05-10T10:00:00Z",
                                "description": "Policy and economy update",
                                "content": "Government policy economy update for India.",
                            }
                        ],
                    },
                ),
            ]
        )

        results = client._fetch_newsdata(
            query="India OR government OR parliament OR economy OR summit OR diplomacy OR science OR environment OR policy",
            country="in",
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(client.session.calls[0]["params"]["country"], "in")
        self.assertEqual(
            client.session.calls[0]["params"]["q"],
            "India OR government OR parliament OR economy OR summit OR diplomacy OR science OR environment OR policy",
        )
        self.assertEqual(
            client.session.calls[1]["params"]["q"],
            "India OR government OR economy OR policy OR parliament OR science",
        )

    def test_article_relevance_rejects_consumer_listicle_titles(self) -> None:
        client = NewsClient(build_settings())
        article = build_article(url="https://www.thehindu.com/example")
        article = Article(
            title="From PMAY to DDA: Government housing schemes every homebuyer should know",
            description="Consumer-focused housing guide",
            url=article.url,
            source="The Hindu",
            published_at=article.published_at,
            content="A guide for homebuyers about housing schemes and loan planning.",
        )

        score = client._article_relevance_score(article)

        self.assertLess(score, 0)

    def test_article_relevance_rejects_local_news_without_national_angle(self) -> None:
        client = NewsClient(
            build_settings(
                preferred_topic_keywords=("government", "policy", "parliament"),
                blocked_topic_keywords=(),
            )
        )
        article = Article(
            title="City traffic police announce local road diversion",
            description="A traffic update for commuters after a road accident.",
            url="https://www.thehindu.com/example",
            source="The Hindu",
            published_at="2026-05-10T10:00:00Z",
            content="Local government officials issued a city news traffic advisory.",
        )

        score = client._article_relevance_score(article)

        self.assertLess(score, 0)


if __name__ == "__main__":
    unittest.main()
