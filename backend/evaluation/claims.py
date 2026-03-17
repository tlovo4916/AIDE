"""Claim extraction and contradiction detection."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from backend.config import settings
from backend.types import Claim, Contradiction
from backend.utils.json_utils import safe_json_loads

if TYPE_CHECKING:
    from backend.llm.router import LLMRouter

logger = logging.getLogger(__name__)

_CLAIM_EXTRACTION_PROMPT = """\
Extract factual claims from the following text. Return a JSON object:
{{"claims": [{{"text": "...", "type": "factual|causal|comparative|definitional", \
"confidence": "strong|moderate|tentative"}}]}}

Only extract concrete, verifiable claims. Omit opinions and vague statements.

Text:
{content}
"""

_CONTRADICTION_CHECK_PROMPT = """\
Given these two claims, determine if they contradict each other.
Return a JSON object:
{{"is_contradictory": true/false, "relationship": "contradictory|nuanced|consistent", \
"explanation": "...", "severity": 0.0-1.0}}

Claim A: {claim_a}
Claim B: {claim_b}
"""

# Negation keywords for keyword-level contradiction detection
_NEGATION_EN = {"not", "no", "never", "neither", "cannot", "doesn't", "don't", "isn't", "aren't"}
_NEGATION_ZH = {"不", "没有", "否", "非", "未", "无"}


class ClaimExtractor:
    """Extract structured claims from artifact content using LLM."""

    def __init__(self, llm_router: LLMRouter, model: str | None = None) -> None:
        self._router = llm_router
        self._model = model or settings.eval_claim_extraction_model

    async def extract(
        self,
        content: str,
        artifact_id: str,
        artifact_type: str = "",
        model: str | None = None,
    ) -> list[Claim]:
        """Extract claims from content via LLM."""
        if not content or not content.strip():
            return []

        use_model = model or self._model
        prompt = _CLAIM_EXTRACTION_PROMPT.format(content=content[:4000])

        try:
            response = await self._router.generate(use_model, prompt, json_mode=True)
        except Exception:
            logger.exception("Claim extraction failed for %s", artifact_id)
            return []

        data = safe_json_loads(response, fallback={})
        raw_claims = data.get("claims", []) if isinstance(data, dict) else []

        claims: list[Claim] = []
        source = f"{artifact_type}/{artifact_id}" if artifact_type else artifact_id
        for raw in raw_claims:
            if not isinstance(raw, dict) or not raw.get("text"):
                continue
            claims.append(
                Claim(
                    claim_id=str(uuid.uuid4())[:8],
                    text=raw["text"],
                    source_artifact=source,
                    claim_type=raw.get("type", ""),
                    confidence=raw.get("confidence", "moderate"),
                )
            )
        return claims


class ContradictionDetector:
    """Detect contradictions between claims using keyword and LLM methods."""

    def __init__(self, llm_router: LLMRouter | None = None, model: str | None = None) -> None:
        self._router = llm_router
        self._model = model or settings.eval_claim_extraction_model

    def detect_keyword(self, claims: list[Claim]) -> list[Contradiction]:
        """Detect contradictions using negation keyword heuristics."""
        contradictions: list[Contradiction] = []
        all_negation = _NEGATION_EN | _NEGATION_ZH

        for i, a in enumerate(claims):
            for j in range(i + 1, len(claims)):
                b = claims[j]
                words_a = set(a.text.lower().split())
                words_b = set(b.text.lower().split())

                # Need enough content overlap to be discussing the same thing
                overlap = words_a & words_b - all_negation
                if len(overlap) < 2:
                    continue

                neg_a = words_a & all_negation
                neg_b = words_b & all_negation
                if neg_a != neg_b and (neg_a or neg_b):
                    contradictions.append(
                        Contradiction(
                            contradiction_id=str(uuid.uuid4())[:8],
                            claim_a=a,
                            claim_b=b,
                            relationship="contradictory",
                            explanation=f"Negation mismatch: {neg_a} vs {neg_b}",
                            severity=0.6,
                            detected_by="keyword",
                        )
                    )
        return contradictions

    async def detect_llm(
        self,
        claims: list[Claim],
        model: str | None = None,
    ) -> list[Contradiction]:
        """Detect contradictions using LLM pairwise comparison.

        Pre-filters pairs by keyword overlap to avoid O(n^2) LLM calls.
        """
        if not self._router or len(claims) < 2:
            return []

        use_model = model or self._model
        contradictions: list[Contradiction] = []

        # Pre-filter: only check pairs with some content overlap
        pairs_to_check: list[tuple[int, int]] = []
        for i in range(len(claims)):
            for j in range(i + 1, len(claims)):
                words_i = set(claims[i].text.lower().split())
                words_j = set(claims[j].text.lower().split())
                overlap = words_i & words_j
                if len(overlap) >= 2:
                    pairs_to_check.append((i, j))

        for i, j in pairs_to_check[:20]:  # Cap at 20 pairs
            prompt = _CONTRADICTION_CHECK_PROMPT.format(
                claim_a=claims[i].text,
                claim_b=claims[j].text,
            )
            try:
                response = await self._router.generate(use_model, prompt, json_mode=True)
            except Exception:
                logger.exception("Contradiction check failed for pair (%d, %d)", i, j)
                continue

            data = safe_json_loads(response, fallback={})
            if not isinstance(data, dict):
                continue
            if data.get("is_contradictory"):
                contradictions.append(
                    Contradiction(
                        contradiction_id=str(uuid.uuid4())[:8],
                        claim_a=claims[i],
                        claim_b=claims[j],
                        relationship=data.get("relationship", "contradictory"),
                        explanation=data.get("explanation", ""),
                        severity=float(data.get("severity", 0.5)),
                        detected_by="llm",
                    )
                )
        return contradictions

    async def detect_all(
        self,
        claims: list[Claim],
        model: str | None = None,
    ) -> list[Contradiction]:
        """Run both keyword and LLM detection, deduplicate results."""
        keyword_results = self.detect_keyword(claims)
        llm_results = await self.detect_llm(claims, model) if self._router else []

        # Deduplicate: if keyword and LLM found the same pair, keep LLM version
        keyword_pairs = set()
        for c in keyword_results:
            pair = frozenset([c.claim_a.claim_id, c.claim_b.claim_id])
            keyword_pairs.add(pair)

        merged = list(keyword_results)
        for c in llm_results:
            pair = frozenset([c.claim_a.claim_id, c.claim_b.claim_id])
            if pair not in keyword_pairs:
                merged.append(c)

        return merged
