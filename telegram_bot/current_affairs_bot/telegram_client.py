import html
import json
import logging
from datetime import datetime

import requests

from current_affairs_bot.config import Settings
from current_affairs_bot.models import Article, GeneratedPost, MCQ


LOGGER = logging.getLogger(__name__)


class TelegramClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()
        self.base_url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}"

    def broadcast(self, article: Article, generated_post: GeneratedPost) -> None:
        message = self._build_post_message(article, generated_post)
        successful_chats = 0
        failures: list[str] = []

        for chat_id in self.settings.chat_ids:
            try:
                self._send_message(chat_id, message)
                if self.settings.telegram_send_mcq_polls:
                    for mcq in generated_post.mcqs[: self.settings.mcqs_per_article]:
                        self._send_quiz(chat_id, mcq)
                elif generated_post.mcqs:
                    self._send_message(chat_id, self._build_mcq_message(generated_post.mcqs))
                successful_chats += 1
            except Exception as exc:
                failures.append(f"{chat_id}: {exc}")
                LOGGER.warning("Telegram delivery failed for chat %s: %s", chat_id, exc)

        if successful_chats == 0 and failures:
            raise RuntimeError("Telegram broadcast failed for all chats. " + " | ".join(failures))
        if failures:
            LOGGER.warning("Telegram broadcast partially succeeded. Failed chats: %s", " | ".join(failures))

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
        self._handle_response(response, "sendMessage")

    def _send_quiz(self, chat_id: str, mcq: MCQ) -> None:
        response = self._post_poll(chat_id, mcq, is_anonymous=False)
        payload = self._response_payload(response)
        description = str(payload.get("description", "")).lower() if isinstance(payload, dict) else ""

        if response.status_code == 400 and "non-anonymous polls can't be sent to channel chats" in description:
            response = self._post_poll(chat_id, mcq, is_anonymous=True)

        self._handle_response(response, "sendPoll")

    def _post_poll(self, chat_id: str, mcq: MCQ, is_anonymous: bool) -> requests.Response:
        return self.session.post(
            f"{self.base_url}/sendPoll",
            data={
                "chat_id": chat_id,
                "question": self._fit_text(mcq.question, 280),
                "options": json.dumps([self._fit_text(option, 90) for option in mcq.options]),
                "type": "quiz",
                "is_anonymous": "true" if is_anonymous else "false",
                "correct_option_id": mcq.answer_index,
                "explanation": self._fit_text(mcq.explanation, 180),
            },
            timeout=self.settings.request_timeout_seconds,
        )

    def _handle_response(self, response: requests.Response, method_name: str) -> None:
        payload = self._response_payload(response)

        if response.status_code == 404:
            raise RuntimeError(
                f"Telegram {method_name} failed with HTTP 404. "
                "This usually means TELEGRAM_BOT_TOKEN is invalid or expired. "
                f"Response: {payload}"
            )

        if response.status_code == 400 and isinstance(payload, dict):
            description = str(payload.get("description", ""))
            if "chat not found" in description.lower():
                raise RuntimeError(
                    f"Telegram {method_name} failed because the target chat was not found. "
                    "This usually means TELEGRAM_GROUP_ID or TELEGRAM_CHANNEL_ID is wrong, "
                    "or the bot has not been added to that chat. "
                    f"Response: {payload}"
                )

        if not response.ok:
            raise RuntimeError(
                f"Telegram {method_name} failed with HTTP {response.status_code}. Response: {payload}"
            )

        if not isinstance(payload, dict) or not payload.get("ok", False):
            raise RuntimeError(f"Telegram {method_name} failed: {payload}")

    def _response_payload(self, response: requests.Response) -> dict | list | str:
        try:
            return response.json()
        except ValueError:
            return {"raw_text": response.text}

    def _build_post_message(self, article: Article, generated_post: GeneratedPost) -> str:
        title = html.escape(generated_post.title)
        summary = html.escape(generated_post.summary)
        why_it_matters = "\n".join(
            f"- {html.escape(point)}" for point in generated_post.why_it_matters
        )
        hashtags = self._build_hashtags(article, generated_post)
        source = html.escape(article.source)
        source_url = html.escape(article.url, quote=True)
        published_at = html.escape(self._format_datetime(article.published_at))
        return (
            "<b>Current Affairs Update</b>\n\n"
            f"<b>{title}</b>\n\n"
            f"<b>Summary:</b>\n{summary}\n\n"
            f"<b>Why it matters for UPSC/SSC:</b>\n{why_it_matters}\n\n"
            f"<b>Source:</b> <a href=\"{source_url}\">{source}</a>\n"
            f"<b>Published:</b> {published_at}\n\n"
            f"{hashtags}"
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

    def _build_hashtags(self, article: Article, generated_post: GeneratedPost) -> str:
        text = " ".join(
            [
                article.title,
                article.description,
                generated_post.title,
                generated_post.summary,
                " ".join(generated_post.why_it_matters),
            ]
        ).lower()

        tags = ["#CurrentAffairs", "#UPSC", "#SSC", "#GK", "#GovtExams"]

        keyword_tags = [
            ("economy", "#Economy"),
            ("budget", "#Economy"),
            ("rbi", "#Economy"),
            ("government", "#Polity"),
            ("parliament", "#Polity"),
            ("bill", "#Polity"),
            ("scheme", "#Schemes"),
            ("science", "#ScienceTech"),
            ("technology", "#ScienceTech"),
            ("space", "#ScienceTech"),
            ("summit", "#InternationalRelations"),
            ("diplomacy", "#InternationalRelations"),
            ("iran", "#InternationalRelations"),
            ("sports", "#Sports"),
            ("environment", "#Environment"),
            ("climate", "#Environment"),
        ]

        for keyword, tag in keyword_tags:
            if keyword in text and tag not in tags:
                tags.append(tag)

        return " ".join(tags[:8])

