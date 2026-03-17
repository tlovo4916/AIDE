"""Shared NLP utilities — stopwords, tokenization helpers."""

from __future__ import annotations

import re

ENGLISH_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "in",
        "on",
        "of",
        "for",
        "to",
        "and",
        "or",
        "is",
        "are",
        "was",
        "were",
        "with",
        "by",
        "at",
        "from",
        "as",
        "it",
        "its",
        "that",
        "this",
        "which",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        "not",
        "no",
        "but",
        "if",
        "than",
        "then",
        "so",
        "very",
        "just",
        "about",
        "into",
    }
)


def tokenize_topic(text: str) -> list[str]:
    """Extract meaningful tokens from topic text, supporting English and Chinese.

    Used by both evaluator.py (topic drift) and metrics.py (evidence mapping).
    """
    tokens: list[str] = []
    # Chinese character segments → bigrams
    chinese_segments = re.findall(r"[\u4e00-\u9fff]+", text)
    for segment in chinese_segments:
        for i in range(len(segment) - 1):
            tokens.append(segment[i : i + 2])
        if len(segment) == 1:
            tokens.append(segment)
    # English words, filtered
    english_words = re.findall(r"[a-zA-Z]{2,}", text)
    for w in english_words:
        low = w.lower()
        if low not in ENGLISH_STOPWORDS:
            tokens.append(low)
    return tokens
