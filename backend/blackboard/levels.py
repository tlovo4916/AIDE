"""Context-level summary generation (L0 ~50 tokens, L1 ~500 tokens)."""

from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable

from backend.types import ArtifactType

logger = logging.getLogger(__name__)

LLMCall = Callable[[list[dict[str, str]]], Awaitable[str]]

_L0_PROMPTS: dict[ArtifactType, str] = {
    ArtifactType.DIRECTIONS: (
        "Summarize this research direction in one sentence (max 50 tokens). "
        "Focus on the core goal and scope.\n\n{content}"
    ),
    ArtifactType.HYPOTHESES: (
        "State this hypothesis in one sentence (max 50 tokens). "
        "Include the main claim and key variables.\n\n{content}"
    ),
    ArtifactType.EVIDENCE_FINDINGS: (
        "Summarize this evidence finding in one sentence (max 50 tokens). "
        "State the main result and its significance.\n\n{content}"
    ),
    ArtifactType.EVIDENCE_GAPS: (
        "Summarize this evidence gap in one sentence (max 50 tokens). "
        "State what is missing and why it matters.\n\n{content}"
    ),
    ArtifactType.EXPERIMENT_GUIDE: (
        "Summarize this experiment guide in one sentence (max 50 tokens). "
        "State the experimental approach.\n\n{content}"
    ),
    ArtifactType.OUTLINE: (
        "Summarize this document outline in one sentence (max 50 tokens). "
        "State the structure and main thesis.\n\n{content}"
    ),
    ArtifactType.DRAFT: (
        "Summarize this draft in one sentence (max 50 tokens). "
        "State the main argument and conclusion.\n\n{content}"
    ),
    ArtifactType.REVIEW: (
        "Summarize this review in one sentence (max 50 tokens). "
        "State the overall assessment and key issues.\n\n{content}"
    ),
}

_L1_PROMPTS: dict[ArtifactType, str] = {
    ArtifactType.DIRECTIONS: (
        "Create a structured JSON overview (max 500 tokens) of this research direction "
        "with keys: title, key_themes, scope, constraints, related_fields.\n\n{content}"
    ),
    ArtifactType.HYPOTHESES: (
        "Create a structured JSON overview (max 500 tokens) of this hypothesis "
        "with keys: statement, variables, assumptions, testability, related_hypotheses.\n\n{content}"
    ),
    ArtifactType.EVIDENCE_FINDINGS: (
        "Create a structured JSON overview (max 500 tokens) of this evidence finding "
        "with keys: finding, methodology, strength, limitations, source_quality.\n\n{content}"
    ),
    ArtifactType.EVIDENCE_GAPS: (
        "Create a structured JSON overview (max 500 tokens) of this evidence gap "
        "with keys: gap_description, importance, potential_sources, search_suggestions.\n\n{content}"
    ),
    ArtifactType.EXPERIMENT_GUIDE: (
        "Create a structured JSON overview (max 500 tokens) of this experiment guide "
        "with keys: objective, methodology, variables, expected_outcomes, resources.\n\n{content}"
    ),
    ArtifactType.OUTLINE: (
        "Create a structured JSON overview (max 500 tokens) of this outline "
        "with keys: thesis, sections, key_arguments, target_audience.\n\n{content}"
    ),
    ArtifactType.DRAFT: (
        "Create a structured JSON overview (max 500 tokens) of this draft "
        "with keys: abstract, main_argument, evidence_used, conclusions, weaknesses.\n\n{content}"
    ),
    ArtifactType.REVIEW: (
        "Create a structured JSON overview (max 500 tokens) of this review "
        "with keys: overall_score, strengths, weaknesses, critical_issues, suggestions.\n\n{content}"
    ),
}

_L0_MAX_CHARS = 200
_L1_MAX_CHARS = 2000


class LevelGenerator:

    def __init__(self, llm_call: LLMCall) -> None:
        self._llm_call = llm_call

    async def generate_l0(self, content_l2: str, artifact_type: ArtifactType) -> str:
        prompt_template = _L0_PROMPTS.get(
            artifact_type, _L0_PROMPTS[ArtifactType.DIRECTIONS]
        )
        prompt = prompt_template.format(content=content_l2)
        try:
            result = await self._llm_call([
                {
                    "role": "system",
                    "content": "You are a concise summarizer. Output only the summary.",
                },
                {"role": "user", "content": prompt},
            ])
            return result.strip()
        except Exception as exc:
            logger.warning("LLM L0 generation failed, using truncation: %s", exc)
            return self._truncate_l0(content_l2)

    async def generate_l1(
        self, content_l2: str, artifact_type: ArtifactType
    ) -> dict[str, Any]:
        prompt_template = _L1_PROMPTS.get(
            artifact_type, _L1_PROMPTS[ArtifactType.DIRECTIONS]
        )
        prompt = prompt_template.format(content=content_l2)
        try:
            result = await self._llm_call([
                {
                    "role": "system",
                    "content": "You are a structured summarizer. Output valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ])
            return json.loads(result.strip())
        except json.JSONDecodeError:
            logger.warning("LLM L1 returned invalid JSON, using truncation")
            return self._truncate_l1(content_l2, artifact_type)
        except Exception as exc:
            logger.warning("LLM L1 generation failed, using truncation: %s", exc)
            return self._truncate_l1(content_l2, artifact_type)

    @staticmethod
    def _truncate_l0(content: str) -> str:
        clean = " ".join(content.split())
        if len(clean) <= _L0_MAX_CHARS:
            return clean
        return clean[: _L0_MAX_CHARS - 3] + "..."

    @staticmethod
    def _truncate_l1(content: str, artifact_type: ArtifactType) -> dict[str, Any]:
        clean = " ".join(content.split())
        truncated = clean[:_L1_MAX_CHARS] if len(clean) > _L1_MAX_CHARS else clean
        return {
            "artifact_type": artifact_type.value,
            "summary": truncated,
            "truncated": len(clean) > _L1_MAX_CHARS,
        }
