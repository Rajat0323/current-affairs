from dataclasses import dataclass
from pathlib import Path
import os
import re

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _optional_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _sanitize_secret_like_value(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _first_present(names: tuple[str, ...], default: str = "") -> str:
    for name in names:
        value = _sanitize_secret_like_value(os.getenv(name, ""))
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


def _csv_env(name: str, default: str = "") -> tuple[str, ...]:
    raw = _optional_env(name, default)
    if not raw:
        return ()
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _validate_telegram_bot_token(value: str) -> str:
    token = _sanitize_secret_like_value(value)
    if not re.match(r"^\d{6,}:[A-Za-z0-9_-]{20,}$", token):
        raise ValueError(
            "TELEGRAM_BOT_TOKEN does not look like a valid BotFather token. "
            "It should look like '123456789:AA...' without quotes or extra spaces."
        )
    return token


def _validate_chat_id(value: str, env_name: str) -> str:
    chat_id = _sanitize_secret_like_value(value)
    if not chat_id:
        return ""
    if chat_id.startswith("@"):
        if not re.match(r"^@[A-Za-z0-9_]{4,}$", chat_id):
            raise ValueError(
                f"{env_name} does not look like a valid Telegram username-based chat id. "
                "Use @channelusername without quotes."
            )
        return chat_id
    if not re.match(r"^-?\d+$", chat_id):
        raise ValueError(
            f"{env_name} does not look like a valid numeric Telegram chat id. "
            "Use values like -1001234567890 without quotes."
        )
    return chat_id


def _validate_public_ref(value: str, env_name: str) -> str:
    ref = _sanitize_secret_like_value(value)
    if not ref:
        return ""
    if ref.startswith("@"):
        if not re.match(r"^@[A-Za-z0-9_]{4,}$", ref):
            raise ValueError(
                f"{env_name} does not look like a valid Telegram username. "
                "Use @channelusername without quotes."
            )
        return ref
    if ref.startswith("https://t.me/"):
        return ref
    raise ValueError(
        f"{env_name} must be either a Telegram username like @channelusername "
        "or a public link like https://t.me/channelusername."
    )


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_channel_id: str
    telegram_group_id: str
    news_api_key: str
    news_api_url: str
    newsdata_api_key: str
    newsdata_api_url: str
    current_affairs_query: str
    newsdata_india_query: str
    newsdata_world_query: str
    newsdata_india_country: str
    preferred_topic_keywords: tuple[str, ...]
    blocked_topic_keywords: tuple[str, ...]
    allowed_source_domains: tuple[str, ...]
    blocked_source_domains: tuple[str, ...]
    minimum_article_relevance_score: int
    max_article_age_hours: int
    news_language: str
    news_page_size: int
    max_articles_per_cycle: int
    poll_interval_minutes: int
    request_timeout_seconds: int
    state_file: Path
    group_reveal_state_file: Path
    openai_api_key: str
    openai_base_url: str
    openai_model: str
    telegram_send_mcq_polls: bool
    mcqs_per_article: int
    telegram_require_group: bool
    telegram_brand_name: str
    telegram_channel_ref: str
    telegram_group_ref: str
    telegram_call_to_action: str
    telegram_discovery_keywords: tuple[str, ...]
    group_answer_delay_minutes: int
    group_discussion_call_to_action: str

    def __post_init__(self) -> None:
        if not self.news_api_key and not self.newsdata_api_key:
            raise ValueError(
                "Set at least one news provider key: NEWS_API_KEY or NEWSDATA_API_KEY."
            )
        if self.telegram_require_group and not self.telegram_group_id:
            raise ValueError(
                "TELEGRAM_GROUP_ID is required because TELEGRAM_REQUIRE_GROUP is enabled. "
                "TELEGRAM_GROUP_REF is only a public link/username and does not send posts by itself."
            )
        if self.telegram_group_ref and not self.telegram_group_id:
            raise ValueError(
                "TELEGRAM_GROUP_REF is set, but TELEGRAM_GROUP_ID is missing. "
                "Use TELEGRAM_GROUP_ID for actual group posting."
            )

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
        reveal_state_relative_path = Path(
            _optional_env("GROUP_REVEAL_STATE_FILE", "data/pending_group_reveals.json")
        )
        return cls(
            telegram_bot_token=_validate_telegram_bot_token(
                _first_present(("TELEGRAM_BOT_TOKEN", "BOT_TOKEN")) or _require_env("TELEGRAM_BOT_TOKEN")
            ),
            telegram_channel_id=_validate_chat_id(
                _first_present(("TELEGRAM_CHANNEL_ID", "CHANNEL_ID")) or _require_env("TELEGRAM_CHANNEL_ID"),
                "TELEGRAM_CHANNEL_ID",
            ),
            telegram_group_id=_validate_chat_id(
                _first_present(("TELEGRAM_GROUP_ID", "GROUP_ID")),
                "TELEGRAM_GROUP_ID",
            ),
            news_api_key=_first_present(("NEWS_API_KEY", "NEWSAPI_KEY")),
            news_api_url=_optional_env("NEWS_API_URL", "https://newsapi.org/v2/everything"),
            newsdata_api_key=_first_present(("NEWSDATA_API_KEY",)),
            newsdata_api_url=_optional_env("NEWSDATA_API_URL", "https://newsdata.io/api/1/latest"),
            current_affairs_query=_optional_env(
                "CURRENT_AFFAIRS_QUERY",
                "India government OR parliament OR national politics OR foreign policy OR international relations",
            ),
            newsdata_india_query=_optional_env(
                "NEWSDATA_INDIA_QUERY",
                "India OR government OR parliament OR politics OR policy",
            ),
            newsdata_world_query=_optional_env(
                "NEWSDATA_WORLD_QUERY",
                "international relations OR diplomacy OR geopolitics OR foreign policy",
            ),
            newsdata_india_country=_optional_env("NEWSDATA_INDIA_COUNTRY", "in"),
            preferred_topic_keywords=_csv_env(
                "PREFERRED_TOPIC_KEYWORDS",
                (
                    "india,indian,national,government,union government,central government,parliament,"
                    "lok sabha,rajya sabha,cabinet,prime minister,president,ministry,supreme court,"
                    "judgment,constitution,constitutional,governance,scheme,policy,bill,act,"
                    "election,election commission,committee,commission,regulation,guideline,"
                    "diplomacy,foreign policy,international relations,geopolitics,bilateral,"
                    "multilateral,defence,security,summit,treaty,agreement,ceasefire,sanction,"
                    "un,united nations,who,wto,imf,world bank,adb,brics,g20,quad,saarc,asean"
                ),
            ),
            blocked_topic_keywords=_csv_env(
                "BLOCKED_TOPIC_KEYWORDS",
                (
                    "celebrity,actor,actress,box office,movie,film trailer,relationship,love life,"
                    "viral,used car,car review,phone review,shopping,deals,quote of the day,travel guide,"
                    "holiday,entertainment,gossip,web3,event promotion,product launch,market report,cagr,"
                    "biopic,fitness method,ufo,astrology,horoscope,reels,instagram,x bio,mother's day,"
                    "wedding look,style tips,skin care,net worth,luxury,launch event,sale today,"
                    "homebuyer,real estate tips,loan emi,buying guide,property advice,"
                    "astrological,dating,weekend watch,celeb,fan war,local news,city news,"
                    "traffic jam,road accident,crime,robbery,murder,shooting,weather update,"
                    "school holiday,train delay,metro delay,water supply,power cut"
                ),
            ),
            allowed_source_domains=_csv_env(
                "ALLOWED_SOURCE_DOMAINS",
                (
                    "thehindu.com,indianexpress.com,pib.gov.in,prsindia.org,business-standard.com,"
                    "livemint.com,thehindubusinessline.com,economictimes.indiatimes.com,"
                    "timesofindia.indiatimes.com,hindustantimes.com,ndtv.com,news18.com,"
                    "down2earth.org.in,moneycontrol.com,financialexpress.com,tribuneindia.com,"
                    "theprint.in,newindianexpress.com,firstpost.com,deccanherald.com"
                ),
            ),
            blocked_source_domains=_csv_env(
                "BLOCKED_SOURCE_DOMAINS",
                (
                    "globenewswire.com,prnewswire.com,news.google.com,gyanhigyan.com,brandiconimage.com,"
                    "digitpatrox.com,asianetnews.com,siasat.com,rediff.com,informalnewz.com,"
                    "goldpricetoday.co.in,collegesearch.in,new7tv.com,cbnc.com,newsable.asianetnews.com"
                ),
            ),
            minimum_article_relevance_score=_int_env("MINIMUM_ARTICLE_RELEVANCE_SCORE", 4),
            max_article_age_hours=_int_env("MAX_ARTICLE_AGE_HOURS", 72),
            news_language=_optional_env("NEWS_LANGUAGE", "en"),
            news_page_size=_int_env("NEWS_PAGE_SIZE", 10),
            max_articles_per_cycle=_int_env("MAX_ARTICLES_PER_CYCLE", 2),
            poll_interval_minutes=_int_env("POLL_INTERVAL_MINUTES", 30),
            request_timeout_seconds=_int_env("REQUEST_TIMEOUT_SECONDS", 30),
            state_file=(BASE_DIR / state_relative_path).resolve(),
            group_reveal_state_file=(BASE_DIR / reveal_state_relative_path).resolve(),
            openai_api_key=_first_present(("OPENAI_API_KEY", "LLM_API_KEY")) or _require_env("OPENAI_API_KEY"),
            openai_base_url=_first_present(("OPENAI_BASE_URL", "LLM_BASE_URL"), "https://api.openai.com/v1"),
            openai_model=_first_present(("OPENAI_MODEL", "LLM_MODEL"), "gpt-4.1-mini"),
            telegram_send_mcq_polls=_bool_env("TELEGRAM_SEND_MCQ_POLLS", True),
            mcqs_per_article=_int_env("MCQS_PER_ARTICLE", 3),
            telegram_require_group=_bool_env("TELEGRAM_REQUIRE_GROUP", True),
            telegram_brand_name=_optional_env("TELEGRAM_BRAND_NAME", "GKShot Daily"),
            telegram_channel_ref=_validate_public_ref(
                _optional_env("TELEGRAM_CHANNEL_REF", "@gkshotdaily"),
                "TELEGRAM_CHANNEL_REF",
            ),
            telegram_group_ref=_validate_public_ref(
                _optional_env("TELEGRAM_GROUP_REF", "@gkshotdaily1"),
                "TELEGRAM_GROUP_REF",
            ),
            telegram_call_to_action=_optional_env(
                "TELEGRAM_CALL_TO_ACTION",
                "Join GKShot Daily for UPSC current affairs quiz, SSC GK MCQ, polity, history, geography, economy, and exam-focused revision.",
            ),
            telegram_discovery_keywords=_csv_env(
                "TELEGRAM_DISCOVERY_KEYWORDS",
                "UPSC current affairs quiz, UPSC GK quiz, daily current affairs MCQ, SSC GK quiz, Indian polity quiz, history GK, geography quiz, UPSC prelims MCQ",
            ),
            group_answer_delay_minutes=_int_env("GROUP_ANSWER_DELAY_MINUTES", 30),
            group_discussion_call_to_action=_optional_env(
                "GROUP_DISCUSSION_CALL_TO_ACTION",
                "Discuss the national or international exam angle from this current affairs update.",
            ),
        )

