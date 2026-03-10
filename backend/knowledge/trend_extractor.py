"""Trend signal extraction from evidence artifacts using LLM."""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

_ENTITY_PROMPT = """\
从以下研究文本中提取关键实体。返回 JSON 数组，每个元素包含:
- "name": 实体名称
- "type": 实体类型 (researcher/method/technology/concept/dataset)
- "first_mentioned_year": 首次提及年份（如有），否则 null

文本:
{text}

仅返回 JSON 数组，不要其他内容。示例:
[{{"name": "Transformer", "type": "technology", "first_mentioned_year": 2017}}]
"""

_TREND_PROMPT = """\
基于以下实体列表和研究证据，分析趋势信号。识别:
1. 上升趋势（rising）：近年频繁出现、引用增加的实体
2. 下降趋势（declining）：逐渐被替代或提及减少的实体
3. 新兴连接（emerging_connection）：不同领域实体之间的新关联

实体列表:
{entities}

研究证据摘要:
{evidence}

返回 JSON 对象:
{{
  "trends": [
    {{
      "signal_type": "rising|declining|emerging_connection",
      "entities": ["实体名1", "实体名2"],
      "description": "趋势描述",
      "confidence": 0.0-1.0,
      "evidence_summary": "支持该趋势的证据摘要"
    }}
  ],
  "summary": "总体趋势概述"
}}

仅返回 JSON，不要其他内容。
"""


@runtime_checkable
class LLMRouter(Protocol):
    async def generate(
        self, model: str, prompt: str, *, system_prompt: str | None = None
    ) -> str: ...


class TrendExtractor:
    """Extracts entities and trend signals from evidence artifacts using LLM."""

    def __init__(self, llm_router: LLMRouter, model: str = "deepseek-chat") -> None:
        self._llm_router = llm_router
        self._model = model

    async def extract_entities(self, text: str) -> list[dict[str, Any]]:
        """Extract named entities from research text."""
        prompt = _ENTITY_PROMPT.format(text=text[:3000])
        try:
            raw = await self._llm_router.generate(self._model, prompt)
            raw = raw.strip()
            # Strip markdown fences
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()
            entities = json.loads(raw)
            if isinstance(entities, list):
                return entities
        except Exception as exc:
            logger.warning("[TrendExtractor] Entity extraction failed: %s", exc)
        return []

    async def extract_trends(
        self,
        entities: list[dict[str, Any]],
        evidence_texts: list[str],
    ) -> dict[str, Any]:
        """Analyze trend signals from entities and evidence."""
        entities_str = json.dumps(entities[:30], ensure_ascii=False, indent=2)
        evidence_str = "\n---\n".join(t[:500] for t in evidence_texts[:10])
        prompt = _TREND_PROMPT.format(entities=entities_str, evidence=evidence_str)
        try:
            raw = await self._llm_router.generate(self._model, prompt)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()
            result = json.loads(raw)
            if isinstance(result, dict):
                return result
        except Exception as exc:
            logger.warning("[TrendExtractor] Trend analysis failed: %s", exc)
        return {"trends": [], "summary": ""}

    async def process_evidence_artifacts(
        self, board: Any
    ) -> dict[str, Any] | None:
        """Full pipeline: collect evidence texts -> extract entities -> analyze trends."""
        from backend.types import ArtifactType, ContextLevel

        try:
            summary = await board.get_state_summary(ContextLevel.L1)
        except Exception:
            return None

        # Collect evidence text blocks from the summary
        evidence_texts: list[str] = []
        # Parse evidence sections from state summary
        lines = summary.split("\n")
        current_block: list[str] = []
        in_evidence = False
        for line in lines:
            if "evidence" in line.lower() and ("##" in line or "**" in line):
                in_evidence = True
                if current_block:
                    evidence_texts.append("\n".join(current_block))
                    current_block = []
                continue
            if in_evidence and line.startswith("##"):
                in_evidence = False
                if current_block:
                    evidence_texts.append("\n".join(current_block))
                    current_block = []
                continue
            if in_evidence and line.strip():
                current_block.append(line)
        if current_block:
            evidence_texts.append("\n".join(current_block))

        if not evidence_texts:
            # Use the full summary as fallback
            evidence_texts = [summary[:2000]]

        all_entities: list[dict[str, Any]] = []
        for text in evidence_texts[:5]:
            entities = await self.extract_entities(text)
            all_entities.extend(entities)

        # Deduplicate entities by name
        seen: set[str] = set()
        unique_entities: list[dict[str, Any]] = []
        for e in all_entities:
            name = e.get("name", "").lower()
            if name and name not in seen:
                seen.add(name)
                unique_entities.append(e)

        if not unique_entities:
            logger.info("[TrendExtractor] No entities found, skipping trend analysis")
            return None

        result = await self.extract_trends(unique_entities, evidence_texts)
        result["entities"] = unique_entities
        return result
