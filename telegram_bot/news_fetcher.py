"""
news_fetcher.py — Fetches and filters UPSC-relevant news from NewsAPI.
"""

import logging
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import config

logger = logging.getLogger(__name__)


def fetch_raw_news(category: str = "general") -> List[Dict]:
    """
    Fetch top headlines from NewsAPI for India.

    Args:
        category: NewsAPI category (general, business, science, technology, health)

    Returns:
        List of raw article dicts from NewsAPI.
    """
    params = {
        "apiKey": config.NEWS_API_KEY,
        "country": config.NEWS_API_COUNTRY,
        "language": config.NEWS_API_LANGUAGE,
        "pageSize": config.NEWS_API_PAGE_SIZE,
        "category": category,
    }

    try:
        response = requests.get(
            config.NEWS_API_BASE_URL,
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "ok":
            logger.error("NewsAPI error: %s", data.get("message", "Unknown error"))
            return []

        articles = data.get("articles", [])
        logger.info("Fetched %d raw articles from NewsAPI (category=%s)", len(articles), category)
        return articles

    except requests.exceptions.ConnectionError:
        logger.error("Network error: Could not connect to NewsAPI")
        return []
    except requests.exceptions.Timeout:
        logger.error("NewsAPI request timed out")
        return []
    except requests.exceptions.HTTPError as e:
        logger.error("NewsAPI HTTP error: %s", e)
        return []
    except Exception as e:
        logger.error("Unexpected error fetching news: %s", e)
        return []


def is_upsc_relevant(article: Dict) -> bool:
    """
    Decide if a news article is relevant for UPSC/SSC exams.

    Strategy:
    1. Block articles that match irrelevant keywords.
    2. Pass articles that match at least one UPSC keyword.

    Args:
        article: NewsAPI article dict.

    Returns:
        True if article is UPSC-relevant, False otherwise.
    """
    title = (article.get("title") or "").lower()
    description = (article.get("description") or "").lower()
    content = (article.get("content") or "").lower()
    combined_text = f"{title} {description} {content}"

    # Block irrelevant topics first
    for keyword in config.IRRELEVANT_KEYWORDS:
        if keyword in combined_text:
            logger.debug("Blocked article (irrelevant keyword '%s'): %s", keyword, title)
            return False

    # Check for UPSC relevance
    for keyword in config.UPSC_RELEVANT_KEYWORDS:
        if keyword in combined_text:
            logger.debug("Accepted article (keyword '%s'): %s", keyword, title)
            return True

    logger.debug("Skipped article (no UPSC match): %s", title)
    return False


def tag_topic(article: Dict) -> str:
    """
    Assign a broad UPSC topic tag to an article based on keyword matching.

    Returns one of: Government Schemes | Economy | International Relations |
                    Environment & Science | Defence | General Awareness
    """
    title = (article.get("title") or "").lower()
    description = (article.get("description") or "").lower()
    text = f"{title} {description}"

    economy_kw = ["gdp", "inflation", "rbi", "sebi", "budget", "fiscal", "monetary",
                  "finance", "export", "import", "trade", "investment", "banking",
                  "insurance", "tax", "gst", "fdi", "economy", "startup"]
    intl_kw = ["bilateral", "summit", "treaty", "mou", "agreement", "united nations",
               "who", "imf", "world bank", "g20", "g7", "brics", "sco", "asean",
               "nato", "geopolitics", "diplomacy", "foreign", "india-"]
    env_kw = ["climate", "environment", "pollution", "wildlife", "forest",
              "biodiversity", "glacier", "carbon", "renewable", "solar", "green",
              "conservation", "tiger", "elephant", "national park"]
    science_kw = ["isro", "space", "satellite", "drdo", "nuclear", "research", "discovery"]
    govt_kw = ["scheme", "policy", "government", "ministry", "cabinet", "parliament",
               "bill", "act", "law", "regulation", "mission", "yojana", "initiative",
               "launch", "commission", "tribunal"]

    if any(k in text for k in economy_kw):
        return "Economy"
    if any(k in text for k in intl_kw):
        return "International Relations"
    if any(k in text for k in env_kw):
        return "Environment"
    if any(k in text for k in science_kw):
        return "Science & Technology"
    if any(k in text for k in govt_kw):
        return "Government Schemes & Policies"
    return "General Awareness"


def fetch_upsc_articles(max_articles: int = None) -> List[Dict]:
    """
    Main function — fetches, filters, and tags UPSC-relevant articles.

    Pulls from multiple NewsAPI categories to improve coverage, then
    deduplicates and limits to max_articles.

    Args:
        max_articles: Override for config.NEWS_API_MAX_ARTICLES.

    Returns:
        List of filtered & enriched article dicts.
    """
    if max_articles is None:
        max_articles = config.NEWS_API_MAX_ARTICLES

    categories = ["general", "business", "science", "technology", "health"]
    all_articles: List[Dict] = []
    seen_titles = set()

    for category in categories:
        raw_articles = fetch_raw_news(category)
        for article in raw_articles:
            title = article.get("title", "").strip()
            if not title or title in seen_titles:
                continue
            if not article.get("description"):
                continue
            if is_upsc_relevant(article):
                article["upsc_topic"] = tag_topic(article)
                article["fetched_category"] = category
                all_articles.append(article)
                seen_titles.add(title)

        if len(all_articles) >= max_articles * 3:
            break

    logger.info("Total UPSC-relevant articles after filtering: %d", len(all_articles))

    # Return top articles by recency (NewsAPI already sorts by publishedAt descending)
    return all_articles[:max_articles]
