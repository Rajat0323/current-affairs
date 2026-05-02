import html
import json
import logging
from datetime import datetime, timedelta, timezone
import uuid

import requests

from current_affairs_bot.config import Settings
from current_affairs_bot.models import Article, GeneratedPost, MCQ, PendingGroupReveal


LOGGER = logging.getLogger(__name__)


class TelegramClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()
        self.base_url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}"

    def broadcast(self, article: Article, generated_post: GeneratedPost) -> list[PendingGroupReveal]:
        pending_reveals: list[PendingGroupReveal] = []
        successful_chats = 0
        failures: list[str] = []

        if self.settings.telegram_channel_id:
            chat_id = self.settings.telegram_channel_id
            try:
                message = self._build_post_message(chat_id, article, generated_post)
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

        if self.settings.telegram_group_id:
            chat_id = self.settings.telegram_group_id
            try:
                pending_reveals = self._post_group_discussions(article, generated_post)
                successful_chats += 1
            except Exception as exc:
                failures.append(f"{chat_id}: {exc}")
                LOGGER.warning("Telegram delivery failed for chat %s: %s", chat_id, exc)

        if successful_chats == 0 and failures:
            raise RuntimeError("Telegram broadcast failed for all chats. " + " | ".join(failures))
        if failures:
            LOGGER.warning("Telegram broadcast partially succeeded. Failed chats: %s", " | ".join(failures))
        return pending_reveals

    def send_group_answer_reveal(self, reveal: PendingGroupReveal) -> None:
        if not self.settings.telegram_group_id:
            return
        self._send_message(self.settings.telegram_group_id, self._build_group_answer_reveal(reveal))

    def _post_group_discussions(self, article: Article, generated_post: GeneratedPost) -> list[PendingGroupReveal]:
        group_id = self.settings.telegram_group_id
        if not group_id:
            return []

        reveals: list[PendingGroupReveal] = []
        self._send_message(group_id, self._build_group_starter_message(generated_post))
        for mcq in generated_post.mcqs[: self.settings.mcqs_per_article]:
            self._send_message(group_id, self._build_group_question_prompt(generated_post, mcq))
            self._send_quiz(group_id, mcq)
            reveals.append(self._build_pending_reveal(generated_post, mcq))
        LOGGER.info(
            "Posted %s discussion prompt(s) and %s poll(s) to the Telegram group for article: %s",
            len(generated_post.mcqs[: self.settings.mcqs_per_article]) + 1,
            len(generated_post.mcqs[: self.settings.mcqs_per_article]),
            article.title,
        )
        return reveals

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

    def _build_post_message(self, chat_id: str, article: Article, generated_post: GeneratedPost) -> str:
        title = html.escape(generated_post.title)
        summary = html.escape(generated_post.summary)
        why_it_matters = "\n".join(
            f"- {html.escape(point)}" for point in generated_post.why_it_matters
        )
        hashtags = self._build_hashtags(article, generated_post)
        discovery_footer = self._build_discovery_footer(chat_id)
        source = html.escape(article.source)
        source_url = html.escape(article.url, quote=True)
        published_at = html.escape(self._format_datetime(article.published_at))
        intro = self._build_intro(chat_id)
        return (
            f"{intro}\n\n"
            f"<b>{title}</b>\n\n"
            f"<b>Summary:</b>\n{summary}\n\n"
            f"<b>Why it matters for UPSC/SSC:</b>\n{why_it_matters}\n\n"
            f"<b>Source:</b> <a href=\"{source_url}\">{source}</a>\n"
            f"<b>Published:</b> {published_at}\n\n"
            f"{discovery_footer}\n\n"
            f"{hashtags}"
        )

    def _build_group_starter_message(self, generated_post: GeneratedPost) -> str:
        why_it_matters = html.escape(generated_post.why_it_matters[0]) if generated_post.why_it_matters else "Important for exam preparation."
        return (
            "<b>Discussion Starter</b>\n\n"
            f"<b>Topic:</b> {html.escape(generated_post.title)}\n"
            f"<b>Exam Focus:</b> {why_it_matters}\n\n"
            f"{html.escape(self.settings.group_discussion_call_to_action)}"
        )

    def _build_group_question_prompt(self, generated_post: GeneratedPost, mcq: MCQ) -> str:
        return (
            "<b>Quick Quiz</b>\n\n"
            f"<b>Topic:</b> {html.escape(generated_post.title)}\n"
            f"<b>Question:</b> {html.escape(mcq.question)}\n\n"
            "Vote in the poll and drop your reason in the chat before the answer reveal."
        )

    def _build_pending_reveal(self, generated_post: GeneratedPost, mcq: MCQ) -> PendingGroupReveal:
        answer_label = ["A", "B", "C", "D"][mcq.answer_index]
        due_at = datetime.now(timezone.utc) + timedelta(minutes=self.settings.group_answer_delay_minutes)
        return PendingGroupReveal(
            reveal_id=uuid.uuid4().hex,
            article_title=generated_post.title,
            question=mcq.question,
            answer_label=answer_label,
            answer_text=mcq.options[mcq.answer_index],
            explanation=mcq.explanation,
            due_at=due_at.isoformat(),
        )

    def _build_group_answer_reveal(self, reveal: PendingGroupReveal) -> str:
        sections = [
            "<b>Answer Reveal</b>",
            "",
            f"<b>Topic:</b> {html.escape(reveal.article_title)}",
            f"<b>Question:</b> {html.escape(reveal.question)}",
            f"<b>Correct Answer:</b> {html.escape(reveal.answer_label)}. {html.escape(reveal.answer_text)}",
            f"<b>Exam Angle:</b> {html.escape(reveal.explanation)}",
            "",
            html.escape(self.settings.group_discussion_call_to_action),
        ]
        if self.settings.telegram_channel_ref:
            sections.extend(["", f"<b>For full summary:</b> {html.escape(self.settings.telegram_channel_ref)}"])
        return "\n".join(sections)

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

        for keyword in self.settings.telegram_discovery_keywords:
            tag = "#" + "".join(ch for ch in keyword.title() if ch.isalnum())
            if len(tag) > 1 and tag not in tags:
                tags.append(tag)

        return " ".join(tags[:10])

    def _build_intro(self, chat_id: str) -> str:
        if chat_id == self.settings.telegram_channel_id:
            return "<b>Current Affairs Update</b>"
        if chat_id == self.settings.telegram_group_id:
            return "<b>Discussion Post</b>"
        return "<b>Current Affairs Update</b>"

    def _build_discovery_footer(self, chat_id: str) -> str:
        lines = [f"<b>{html.escape(self.settings.telegram_brand_name)}</b>"]

        if self.settings.telegram_call_to_action:
            lines.append(html.escape(self.settings.telegram_call_to_action))

        if chat_id == self.settings.telegram_channel_id and self.settings.telegram_group_ref:
            lines.append(f"<b>Discuss:</b> {html.escape(self.settings.telegram_group_ref)}")
        elif chat_id == self.settings.telegram_group_id and self.settings.telegram_channel_ref:
            lines.append(f"<b>Follow Channel:</b> {html.escape(self.settings.telegram_channel_ref)}")

        if self.settings.telegram_channel_ref:
            lines.append(f"<b>Channel:</b> {html.escape(self.settings.telegram_channel_ref)}")

        if self.settings.telegram_group_ref:
            lines.append(f"<b>Discussion Group:</b> {html.escape(self.settings.telegram_group_ref)}")

        if self.settings.telegram_discovery_keywords:
            keywords = ", ".join(html.escape(item) for item in self.settings.telegram_discovery_keywords[:6])
            lines.append(f"<b>Topics:</b> {keywords}")

        return "\n".join(lines)

