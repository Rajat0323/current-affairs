from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _optional_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _first_present(names: tuple[str, ...], default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer.") from exc


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name, str(default)).strip().lower()
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_channel_id: str
    telegram_group_id: str
    news_api_key: str
    news_api_url: str
    current_affairs_query: str
    news_language: str
    news_page_size: int
    max_articles_per_cycle: int
    poll_interval_minutes: int
    request_timeout_seconds: int
    state_file: Path
    openai_api_key: str
    openai_base_url: str
    openai_model: str
    telegram_send_mcq_polls: bool
    mcqs_per_article: int

    @property
    def chat_ids(self) -> list[str]:
        seen: set[str] = set()
        chat_ids: list[str] = []
        for chat_id in (self.telegram_channel_id, self.telegram_group_id):
            if chat_id and chat_id not in seen:
                seen.add(chat_id)
                chat_ids.append(chat_id)
        return chat_ids

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(BASE_DIR / ".env")
        state_relative_path = Path(_optional_env("STATE_FILE", "data/posted_articles.json"))
        return cls(
            telegram_bot_token=_first_present(("TELEGRAM_BOT_TOKEN", "BOT_TOKEN")) or _require_env("TELEGRAM_BOT_TOKEN"),
            telegram_channel_id=_first_present(("TELEGRAM_CHANNEL_ID", "CHANNEL_ID")) or _require_env("TELEGRAM_CHANNEL_ID"),
            telegram_group_id=_first_present(("TELEGRAM_GROUP_ID", "GROUP_ID")),
            news_api_key=_first_present(("NEWS_API_KEY", "NEWSAPI_KEY")) or _require_env("NEWS_API_KEY"),
            news_api_url=_optional_env("NEWS_API_URL", "https://newsapi.org/v2/everything"),
            current_affairs_query=_optional_env(
                "CURRENT_AFFAIRS_QUERY",
                "India OR government OR parliament OR economy OR summit OR diplomacy OR science OR sports",
            ),
            news_language=_optional_env("NEWS_LANGUAGE", "en"),
            news_page_size=_int_env("NEWS_PAGE_SIZE", 10),
            max_articles_per_cycle=_int_env("MAX_ARTICLES_PER_CYCLE", 2),
            poll_interval_minutes=_int_env("POLL_INTERVAL_MINUTES", 30),
            request_timeout_seconds=_int_env("REQUEST_TIMEOUT_SECONDS", 30),
            state_file=(BASE_DIR / state_relative_path).resolve(),
            openai_api_key=_first_present(("OPENAI_API_KEY", "LLM_API_KEY")) or _require_env("OPENAI_API_KEY"),
            openai_base_url=_first_present(("OPENAI_BASE_URL", "LLM_BASE_URL"), "https://api.openai.com/v1"),
            openai_model=_first_present(("OPENAI_MODEL", "LLM_MODEL"), "gpt-4.1-mini"),
            telegram_send_mcq_polls=_bool_env("TELEGRAM_SEND_MCQ_POLLS", True),
            mcqs_per_article=_int_env("MCQS_PER_ARTICLE", 3),
        )

