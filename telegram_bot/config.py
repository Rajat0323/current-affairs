"""
config.py — Central configuration for UPSC Current Affairs Bot.
Loads all settings from environment variables for security.
"""

import os
from dotenv import load_dotenv

# Load .env file if present (for local development)
load_dotenv()


# ──────────────────────────────────────────────
# API Keys & Credentials
# ──────────────────────────────────────────────

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")  # e.g. @mychannel or -100xxxxxxxxxx

# Optional: OpenAI key for smarter formatting (falls back to rule-based if missing)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


# ──────────────────────────────────────────────
# NewsAPI Settings
# ──────────────────────────────────────────────

NEWS_API_BASE_URL = "https://newsapi.org/v2/top-headlines"
NEWS_API_COUNTRY = "in"          # India
NEWS_API_LANGUAGE = "en"
NEWS_API_PAGE_SIZE = 30          # Fetch up to 30 articles per call
NEWS_API_MAX_ARTICLES = 5        # Max articles to send in one session


# ──────────────────────────────────────────────
# Topic Filters
# ──────────────────────────────────────────────

# Keywords that qualify a news article as UPSC-relevant
UPSC_RELEVANT_KEYWORDS = [
    # Government & Policy
    "scheme", "policy", "government", "ministry", "cabinet", "parliament",
    "bill", "act", "law", "regulation", "mission", "yojana", "initiative",
    "launch", "commission", "tribunal", "supreme court", "high court",
    "election commission", "niti aayog",

    # Economy
    "economy", "gdp", "inflation", "rbi", "sebi", "budget", "fiscal",
    "monetary", "finance", "export", "import", "trade", "investment",
    "startup", "banking", "insurance", "tax", "gst", "fdi", "disinvestment",

    # International Relations
    "india-", "bilateral", "summit", "treaty", "mou", "agreement",
    "united nations", "who", "imf", "world bank", "g20", "g7", "brics",
    "sco", "asean", "nato", "geopolitics", "diplomacy", "foreign",

    # Environment & Science
    "climate", "environment", "pollution", "wildlife", "forest", "biodiversity",
    "glacier", "carbon", "renewable", "solar", "green", "conservation",
    "tiger", "elephant", "national park", "isro", "space", "satellite",
    "drdo", "defense", "nuclear",

    # Social / Awards
    "award", "bharat ratna", "padma", "nobel", "unesco", "heritage",
    "constitution", "amendment", "reservation", "welfare",
]

# Keywords that mark a news article as irrelevant (blocklist)
IRRELEVANT_KEYWORDS = [
    "bollywood", "cricket", "celebrity", "gossip", "murder", "rape", "crime",
    "accident", "film", "movie", "actor", "actress", "ipl", "match",
    "entertainment", "box office", "song", "album", "dating", "wedding",
    "divorce", "viral", "meme", "troll", "fashion", "style", "beauty",
    "horoscope", "astrology", "reality show",
]


# ──────────────────────────────────────────────
# Scheduler Timing (24-hour format, IST)
# ──────────────────────────────────────────────

MORNING_HOUR = 7     # 7:00 AM IST — Daily Current Affairs Summary
MORNING_MINUTE = 0

AFTERNOON_HOUR = 13  # 1:00 PM IST — MCQ Quiz
AFTERNOON_MINUTE = 0

EVENING_HOUR = 19    # 7:00 PM IST — Revision Points
EVENING_MINUTE = 0


# ──────────────────────────────────────────────
# Telegram Formatting
# ──────────────────────────────────────────────

MAX_MESSAGE_LENGTH = 4000   # Telegram limit is 4096 chars
PARSE_MODE = "HTML"         # Use HTML for bold/italic in Telegram


# ──────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────

def validate_config():
    """Raise clear errors if required env vars are missing."""
    missing = []
    if not NEWS_API_KEY:
        missing.append("NEWS_API_KEY")
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_CHANNEL_ID:
        missing.append("TELEGRAM_CHANNEL_ID")
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Copy .env.example to .env and fill in your credentials."
        )
