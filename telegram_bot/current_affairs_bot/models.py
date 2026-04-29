from dataclasses import dataclass


@dataclass(frozen=True)
class Article:
    title: str
    description: str
    url: str
    source: str
    published_at: str
    content: str


@dataclass(frozen=True)
class MCQ:
    question: str
    options: list[str]
    answer_index: int
    explanation: str


@dataclass(frozen=True)
class GeneratedPost:
    title: str
    summary: str
    why_it_matters: list[str]
    mcqs: list[MCQ]

