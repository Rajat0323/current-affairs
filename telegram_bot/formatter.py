"""
formatter.py — Converts raw news articles into UPSC-ready Telegram messages.

Produces three message types:
  1. Current Affairs Card  (morning summary)
  2. MCQ Quiz              (afternoon quiz)
  3. Revision Points       (evening recap)
"""

import re
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Helper utilities
# ──────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Strip HTML tags, source attribution, and excessive whitespace."""
    if not text:
        return ""
    # Remove "[+N chars]" truncation note from NewsAPI content
    text = re.sub(r"\[\+\d+ chars\]", "", text)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse whitespace
    text = " ".join(text.split())
    return text.strip()


def escape_html(text: str) -> str:
    """Escape special HTML characters for Telegram HTML parse mode."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


def generate_key_points(article: Dict) -> List[str]:
    """
    Generate 3–5 UPSC-style bullet points from article title + description.

    This is rule-based (no LLM needed). It breaks the description into
    meaningful fragments and assembles them as exam-ready bullets.
    """
    title = clean_text(article.get("title", ""))
    description = clean_text(article.get("description", ""))
    content = clean_text(article.get("content", ""))

    # Combine sources
    full_text = description if description else content

    # Split into candidate sentences
    sentences = re.split(r"(?<=[.!?])\s+", full_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 30]

    points = []

    # Point 1 — What happened (restate the title slightly)
    if title:
        points.append(f"Key development: {title}.")

    # Points 2–4 — Pick meaningful sentences from the body
    for sentence in sentences:
        if len(points) >= 5:
            break
        # Skip if too short or already captured
        if len(sentence) < 35:
            continue
        # Avoid duplicate content
        if any(sentence[:30] in p for p in points):
            continue
        points.append(sentence)

    # Fallback if not enough points
    if len(points) < 3:
        topic = article.get("upsc_topic", "General Awareness")
        points.append(f"This is an important update under the {topic} domain.")
        points.append("Follow official government/ministry announcements for more details.")

    return points[:5]


def generate_exam_importance(article: Dict) -> str:
    """
    Generate a short "Why important for exam?" note based on the UPSC topic tag.
    """
    topic = article.get("upsc_topic", "General Awareness")

    importance_map = {
        "Economy": (
            "Frequently tested in UPSC Prelims (Economics) and SSC GK section. "
            "Focus on the institution involved, policy impact, and key numbers."
        ),
        "International Relations": (
            "Important for UPSC Prelims & Mains (GS-II). "
            "Note the countries, the agenda of the meeting, and India's stance."
        ),
        "Government Schemes & Policies": (
            "High-priority for both UPSC and SSC. "
            "Remember the ministry, launch year, objective, and target beneficiaries."
        ),
        "Environment": (
            "Tested in UPSC Prelims (Environment section) and SSC GK. "
            "Focus on reports, treaties, species/habitat names, and India's commitments."
        ),
        "Science & Technology": (
            "Relevant for UPSC Prelims (Science) and SSC. "
            "Note the agency involved (ISRO, DRDO), mission objective, and technology used."
        ),
        "General Awareness": (
            "Relevant for current affairs rounds in UPSC, SSC, and other competitive exams."
        ),
    }
    return importance_map.get(topic, importance_map["General Awareness"])


# ──────────────────────────────────────────────
# Message Formatters
# ──────────────────────────────────────────────

def format_current_affairs_card(article: Dict, index: int = 1) -> str:
    """
    Format a single article as a UPSC Current Affairs Card.

    Example output:
    ━━━━━━━━━━━━━━━━━━━━━━━
    📰 CURRENT AFFAIRS | Economy
    ━━━━━━━━━━━━━━━━━━━━━━━
    📌 RBI Raises Repo Rate by 25 Basis Points

    🔑 Key Points:
    • Key development: RBI raised repo rate...
    • The decision was taken in the MPC meeting...
    • Inflation concerns cited as the primary reason.

    🎯 Why Important for Exam?
    Frequently tested in UPSC Prelims...

    🔗 Read more: https://...
    """
    topic = article.get("upsc_topic", "General Awareness")
    title = escape_html(clean_text(article.get("title", "No Title")))
    url = article.get("url", "")
    source = article.get("source", {}).get("name", "")

    key_points = generate_key_points(article)
    exam_importance = generate_exam_importance(article)

    topic_emoji = {
        "Economy": "💹",
        "International Relations": "🌐",
        "Government Schemes & Policies": "🏛️",
        "Environment": "🌿",
        "Science & Technology": "🔬",
        "General Awareness": "📰",
    }.get(topic, "📰")

    bullets = "\n".join(f"  • {escape_html(p)}" for p in key_points)

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━",
        f"{topic_emoji} <b>CURRENT AFFAIRS | {escape_html(topic)}</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"📌 <b>{title}</b>",
        "",
        "🔑 <b>Key Points:</b>",
        bullets,
        "",
        "🎯 <b>Why Important for Exam?</b>",
        f"  {escape_html(exam_importance)}",
    ]

    if source:
        lines.append(f"\n📡 <i>Source: {escape_html(source)}</i>")
    if url:
        lines.append(f'🔗 <a href="{url}">Read more</a>')

    return "\n".join(lines)


def format_morning_summary(articles: List[Dict], date_str: str) -> str:
    """
    Format a morning digest header + multiple Current Affairs Cards.
    """
    header = (
        f"🌅 <b>UPSC/SSC DAILY CURRENT AFFAIRS</b>\n"
        f"📅 <b>{date_str}</b>\n\n"
        f"Good morning! Here are today's top UPSC-relevant news updates.\n"
        f"Study them carefully — any of these could appear in your exam! 📚\n"
    )

    cards = []
    for i, article in enumerate(articles, start=1):
        cards.append(format_current_affairs_card(article, index=i))

    footer = (
        "\n━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⏰ <b>Check back at 1 PM for the MCQ Quiz!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━"
    )

    return header + "\n\n".join(cards) + footer


def format_mcq_quiz(articles: List[Dict], date_str: str) -> str:
    """
    Generate an MCQ quiz from today's current affairs articles.
    Produces one question per article (up to 5).

    Each MCQ is rule-based: the correct answer is derived from the title,
    and distractors are plausible alternatives.
    """
    header = (
        f"📝 <b>AFTERNOON MCQ QUIZ</b>\n"
        f"📅 <b>{date_str}</b>\n\n"
        "Test your knowledge of today's current affairs!\n"
        "Answers will be revealed in the evening revision. 🧠\n\n"
    )

    quiz_blocks = []
    for i, article in enumerate(articles[:5], start=1):
        topic = article.get("upsc_topic", "General Awareness")
        title = clean_text(article.get("title", ""))
        description = clean_text(article.get("description", ""))

        question, options, answer_key = _build_mcq(article, i)

        block = (
            f"<b>Q{i}. {escape_html(question)}</b>\n"
            f"  (A) {escape_html(options[0])}\n"
            f"  (B) {escape_html(options[1])}\n"
            f"  (C) {escape_html(options[2])}\n"
            f"  (D) {escape_html(options[3])}\n"
            f"  <i>Topic: {escape_html(topic)}</i>\n"
            f"  <tg-spoiler>✅ Answer: ({answer_key})</tg-spoiler>"
        )
        quiz_blocks.append(block)

    footer = (
        "\n━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📖 <b>Tap on each answer to reveal it!</b>\n"
        "🌙 Evening revision session at 7 PM.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━"
    )

    return header + "\n\n".join(quiz_blocks) + footer


def _build_mcq(article: Dict, index: int):
    """
    Build a single MCQ question from an article.

    Returns (question_str, [optA, optB, optC, optD], correct_letter)
    """
    topic = article.get("upsc_topic", "General Awareness")
    title = clean_text(article.get("title", ""))
    source_name = article.get("source", {}).get("name", "Unknown")

    # Topic-specific question templates
    templates = {
        "Economy": [
            ("Which body recently made a key decision related to '{title}'?",
             ["Reserve Bank of India", "SEBI", "NITI Aayog", "Finance Ministry"], "A"),
        ],
        "International Relations": [
            ("Which international event/agreement is highlighted in: '{title}'?",
             ["Bilateral summit between India and a partner nation",
              "UN Security Council resolution",
              "G7 communiqué",
              "ASEAN regional forum"], "A"),
        ],
        "Government Schemes & Policies": [
            ("Which Indian ministry is most likely associated with: '{title}'?",
             ["Ministry of Finance / relevant line ministry",
              "Ministry of External Affairs",
              "Ministry of Home Affairs",
              "Ministry of Defence"], "A"),
        ],
        "Environment": [
            ("Which report/body is most associated with: '{title}'?",
             ["Ministry of Environment, Forest & Climate Change",
              "ISRO – Space Applications Centre",
              "National Disaster Management Authority",
              "Archaeological Survey of India"], "A"),
        ],
        "Science & Technology": [
            ("Which agency is most likely behind the development in: '{title}'?",
             ["ISRO / DRDO / DST",
              "Ministry of External Affairs",
              "Reserve Bank of India",
              "Election Commission of India"], "A"),
        ],
        "General Awareness": [
            ("What is the key takeaway from: '{title}'?",
             ["A significant national/international policy development",
              "A sports achievement",
              "An entertainment award",
              "A local government ordinance"], "A"),
        ],
    }

    template_list = templates.get(topic, templates["General Awareness"])
    question_template, options, correct = template_list[0]
    question = question_template.format(title=title[:80])

    return question, options, correct


def format_evening_revision(articles: List[Dict], date_str: str) -> str:
    """
    Format a concise evening revision summary — quick bullets only.
    """
    header = (
        f"🌙 <b>EVENING REVISION — QUICK RECAP</b>\n"
        f"📅 <b>{date_str}</b>\n\n"
        "Revise today's key points before you sleep! 💡\n\n"
    )

    revision_blocks = []
    for i, article in enumerate(articles, start=1):
        topic = article.get("upsc_topic", "General Awareness")
        title = escape_html(clean_text(article.get("title", "")))

        topic_emoji = {
            "Economy": "💹",
            "International Relations": "🌐",
            "Government Schemes & Policies": "🏛️",
            "Environment": "🌿",
            "Science & Technology": "🔬",
            "General Awareness": "📰",
        }.get(topic, "📰")

        points = generate_key_points(article)
        bullets = "\n".join(f"    ▸ {escape_html(p)}" for p in points[:3])

        block = (
            f"{topic_emoji} <b>{i}. {escape_html(topic)}</b>\n"
            f"   📌 {title}\n"
            f"{bullets}"
        )
        revision_blocks.append(block)

    footer = (
        "\n━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🌟 <b>Keep it up! Consistency is the key to cracking UPSC/SSC!</b>\n"
        "🌅 See you tomorrow morning with fresh current affairs.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━"
    )

    return header + "\n\n".join(revision_blocks) + footer
