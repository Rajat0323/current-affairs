import html
import json
from datetime import datetime

import requests

from current_affairs_bot.config import Settings
from current_affairs_bot.models import Article, GeneratedPost, MCQ


class TelegramClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()
        self.base_url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}"

    def broadcast(self, article: Article, generated_post: GeneratedPost) -> None:
        message = self._build_post_message(article, generated_post)
        for chat_id in self.settings.chat_ids:
            self._send_message(chat_id, message)
            if self.settings.telegram_send_mcq_polls:
                for mcq in generated_post.mcqs[: self.settings.mcqs_per_article]:
                    self._send_quiz(chat_id, mcq)
            elif generated_post.mcqs:
                self._send_message(chat_id, self._build_mcq_message(generated_post.mcqs))

    def _send_message(self, chat_id: str, text: str) -> None:
        response = self.session.post(
            f"{self.base_url}/sendMessage",
            data={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": "false",
            },
            timeout=self.settings.request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok", False):
            raise RuntimeError(f"Telegram sendMessage failed: {payload}")

    def _send_quiz(self, chat_id: str, mcq: MCQ) -> None:
        response = self.session.post(
            f"{self.base_url}/sendPoll",
            data={
                "chat_id": chat_id,
                "question": self._fit_text(mcq.question, 280),
                "options": json.dumps([self._fit_text(option, 90) for option in mcq.options]),
                "type": "quiz",
                "is_anonymous": "false",
                "correct_option_id": mcq.answer_index,
                "explanation": self._fit_text(mcq.explanation, 180),
            },
            timeout=self.settings.request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok", False):
            raise RuntimeError(f"Telegram sendPoll failed: {payload}")

    def _build_post_message(self, article: Article, generated_post: GeneratedPost) -> str:
        title = html.escape(generated_post.title)
        summary = html.escape(generated_post.summary)
        why_it_matters = "\n".join(
            f"- {html.escape(point)}" for point in generated_post.why_it_matters
        )
        source = html.escape(article.source)
        source_url = html.escape(article.url, quote=True)
        published_at = html.escape(self._format_datetime(article.published_at))
        return (
            "<b>Current Affairs Update</b>\n\n"
            f"<b>{title}</b>\n\n"
            f"<b>Summary:</b>\n{summary}\n\n"
            f"<b>Why it matters for UPSC/SSC:</b>\n{why_it_matters}\n\n"
            f"<b>Source:</b> <a href=\"{source_url}\">{source}</a>\n"
            f"<b>Published:</b> {published_at}"
        )

    def _build_mcq_message(self, mcqs: list[MCQ]) -> str:
        sections: list[str] = ["<b>Practice MCQs</b>"]
        labels = ["A", "B", "C", "D"]
        for index, mcq in enumerate(mcqs, start=1):
            options = "\n".join(
                f"{labels[option_index]}. {html.escape(option)}"
                for option_index, option in enumerate(mcq.options)
            )
            answer = labels[mcq.answer_index]
            sections.append(
                f"\n<b>{index}. {html.escape(mcq.question)}</b>\n"
                f"{options}\n"
                f"Answer: {answer}\n"
                f"Explanation: {html.escape(mcq.explanation)}"
            )
        return "\n".join(sections)

    def _format_datetime(self, value: str) -> str:
        if not value:
            return "Unknown"
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%d %b %Y %H:%M UTC")
        except ValueError:
            return value

    def _fit_text(self, value: str, limit: int) -> str:
        value = value.strip()
        if len(value) <= limit:
            return value
        return value[: limit - 3].rstrip() + "..."

