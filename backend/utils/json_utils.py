"""Unified JSON parsing with markdown fence stripping."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(
    r"```(?:json|JSON)?\s*\n?(.*?)```",
    re.DOTALL,
)

_PREFIX_RE = re.compile(
    r"^[^{\[]*?([\{\[])",
    re.DOTALL,
)


def safe_json_loads(text: str, fallback: Any = None) -> Any:
    """Strip markdown fences, normalize, and parse JSON. Return fallback on failure."""
    if not text or not text.strip():
        return fallback

    cleaned = text.strip()

    # 1. Strip markdown fences (```json ... ``` or ``` ... ```)
    fence_match = _FENCE_RE.search(cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    # 2. Try direct parse first
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass

    # 3. Strip possible prefix text before JSON (LLM sometimes adds explanation)
    prefix_match = _PREFIX_RE.match(cleaned)
    if prefix_match:
        start = prefix_match.start(1)
        candidate = cleaned[start:]
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            pass

    # 4. Log and return fallback
    snippet = text[:200].replace("\n", "\\n")
    logger.warning("safe_json_loads: failed to parse JSON, text starts with: %s", snippet)
    return fallback
