"""Context builder with token-budget management.

Falls back from L2 (full) -> L1 (overview) -> L0 (abstracts) until the
assembled context fits within the configured token budget.  This prevents
LLM context overflows on large projects without discarding content structure.
"""

from __future__ import annotations

import logging
from typing import Protocol

import tiktoken

from backend.config import settings
from backend.types import ArtifactType, ContextLevel

logger = logging.getLogger(__name__)

_ENCODER = tiktoken.encoding_for_model("text-embedding-3-small")


def _count_tokens(text: str) -> int:
    return len(_ENCODER.encode(text))


class _BoardContextProtocol(Protocol):
    async def get_state_summary(
        self,
        level: ContextLevel,
        relevant_types: set[ArtifactType] | None = None,
    ) -> str: ...


async def build_budget_context(
    board: _BoardContextProtocol,
    budget: int | None = None,
    relevant_types: set[ArtifactType] | None = None,
) -> str:
    """Build a context string that fits within *budget* tokens.

    Degradation strategy:
      L2 (full artifact content)   -> try first
      L1 (structured JSON overview) -> fallback if L2 too large
      L0 (one-line abstracts)       -> fallback if L1 too large
      Hard truncate                 -> last resort
    """
    budget = budget or settings.context_budget_tokens

    for level in (ContextLevel.L2, ContextLevel.L1, ContextLevel.L0):
        summary = await board.get_state_summary(level, relevant_types=relevant_types)
        token_count = _count_tokens(summary)
        if token_count <= budget:
            if level != ContextLevel.L2:
                logger.info(
                    "[ContextBuilder] Using %s (%d tokens, budget=%d)",
                    level.value,
                    token_count,
                    budget,
                )
            return summary
        logger.debug(
            "[ContextBuilder] %s too large (%d tokens), trying lower level",
            level.value,
            token_count,
        )

    # All levels exceed budget — hard truncate L0 (approx 4 chars/token)
    summary = await board.get_state_summary(ContextLevel.L0, relevant_types=relevant_types)
    char_budget = budget * 4
    if len(summary) > char_budget:
        logger.warning(
            "[ContextBuilder] Even L0 exceeds budget (%d tokens). Hard truncating.",
            _count_tokens(summary),
        )
        return summary[:char_budget] + "\n... [CONTEXT TRUNCATED DUE TO TOKEN BUDGET]"
    return summary
