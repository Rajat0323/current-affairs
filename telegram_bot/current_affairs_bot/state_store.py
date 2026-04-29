import json
from datetime import datetime, timezone
from pathlib import Path

from current_affairs_bot.models import Article


class StateStore:
    def __init__(self, path: Path, max_items: int = 1000) -> None:
        self.path = path
        self.max_items = max_items
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def was_posted(self, article: Article) -> bool:
        state = self._load()
        return article.url in state

    def posted_urls(self) -> set[str]:
        return set(self._load().keys())

    def mark_posted(self, article: Article) -> None:
        state = self._load()
        state[article.url] = {
            "title": article.title,
            "posted_at": datetime.now(timezone.utc).isoformat(),
        }
        while len(state) > self.max_items:
            oldest_key = next(iter(state))
            state.pop(oldest_key)
        self._save(state)

    def _load(self) -> dict[str, dict[str, str]]:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _save(self, payload: dict[str, dict[str, str]]) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2)

