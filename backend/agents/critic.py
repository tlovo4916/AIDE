"""Critic agent -- quality review, consistency check, and scoring."""

from __future__ import annotations

import logging
import re

from backend.agents.base import BaseAgent
from backend.types import AgentResponse, AgentRole, AgentTask, ArtifactType, ResearchPhase

logger = logging.getLogger(__name__)

# Phase-specific review framework checklists
_PHASE_REVIEW_CHECKLISTS: dict[str, list[str]] = {
    ResearchPhase.EXPLORE.value: [
        "Coverage: Are key papers and authors identified?",
        "Scope: Is the research scope well-defined?",
        "Gaps: Are open questions explicitly listed?",
    ],
    ResearchPhase.HYPOTHESIZE.value: [
        "Testability: Are hypotheses specific and testable?",
        "Grounding: Are hypotheses grounded in literature?",
        "Novelty: Do hypotheses offer new perspectives?",
    ],
    ResearchPhase.EVIDENCE.value: [
        "Sufficiency: Is there enough evidence per hypothesis?",
        "Quality: Are sources peer-reviewed or reputable?",
        "Contradictions: Are conflicting findings addressed?",
    ],
    ResearchPhase.COMPOSE.value: [
        "Structure: Does the paper follow academic conventions?",
        "Argumentation: Is the logic clear and coherent?",
        "Citations: Are all claims properly cited?",
    ],
    ResearchPhase.COMPLETE.value: [
        "Completeness: Are all sections present and polished?",
        "Consistency: Is terminology used consistently?",
        "Contribution: Is the contribution clearly stated?",
    ],
}


class CriticAgent(BaseAgent):
    role = AgentRole.CRITIC
    system_prompt_template = "critic.j2"
    preferred_model = "deepseek-reasoner"
    primary_artifact_types = [ArtifactType.REVIEW]
    dependency_artifact_types = [
        ArtifactType.DIRECTIONS,
        ArtifactType.HYPOTHESES,
        ArtifactType.EVIDENCE_FINDINGS,
        ArtifactType.EVIDENCE_GAPS,
        ArtifactType.EXPERIMENT_GUIDE,
        ArtifactType.TREND_SIGNALS,
        ArtifactType.OUTLINE,
        ArtifactType.DRAFT,
    ]
    challengeable_roles = [
        AgentRole.DIRECTOR,
        AgentRole.SCIENTIST,
        AgentRole.LIBRARIAN,
        AgentRole.WRITER,
    ]
    can_spawn_subagents = False

    async def pre_execute(self, context: str, task: AgentTask) -> str:
        """Inject phase-specific review framework + evaluation data if available."""
        enriched = context

        # Detect current phase from task description
        phase_value = ""
        phase_enum = None
        for pv in ResearchPhase:
            if pv.value in task.description.lower():
                phase_value = pv.value
                phase_enum = pv
                break

        # Inject evaluation data from EvaluatorService (Phase 3)
        if self._evaluator and phase_enum:
            try:
                eval_lines = await self._build_eval_summary(phase_enum)
                if eval_lines:
                    enriched += "\n" + "\n".join(eval_lines)
            except Exception as exc:
                logger.debug("[Critic] Eval summary failed: %s", exc)

        checklist = _PHASE_REVIEW_CHECKLISTS.get(phase_value)
        if checklist:
            lines = ["\n## Review Framework (phase-specific checklist)"]
            for item in checklist:
                lines.append(f"  - [ ] {item}")
            enriched += "\n" + "\n".join(lines)

        return enriched

    async def _build_eval_summary(self, phase: ResearchPhase) -> list[str]:
        """Build evaluation summary from EvaluatorService store (no LLM call)."""
        lines: list[str] = ["\n## Evaluation Data (automated metrics)"]
        evaluator = self._evaluator

        # Try reading the most recent evaluation from DB store
        if hasattr(evaluator, "_store") and evaluator._store:
            store = evaluator._store
            try:
                from backend.evaluation.store import EvaluationStore
                if isinstance(store, EvaluationStore):
                    results = await store.load_latest(self._project_id, phase.value)
                    if results:
                        lines.append(f"  Composite score: {results.composite_score:.2f}")
                        for dim_name, dim_score in results.dimensions.items():
                            val = dim_score.get("combined", dim_score.get("computable_value"))
                            if val is not None:
                                lines.append(f"  {dim_name}: {val:.2f}")
                        return lines
            except Exception:
                pass

        # Fallback: use information gain detector if available
        if hasattr(evaluator, "_info_gain") and evaluator._info_gain:
            try:
                metric = evaluator._info_gain.compute()
                lines.append(f"  Information gain: {metric.information_gain:.3f}")
                if metric.is_diminishing:
                    lines.append("  ⚠️ Diminishing returns detected")
                if metric.is_loop_detected:
                    lines.append("  ⚠️ Loop detected (repetitive content)")
                return lines
            except Exception:
                pass

        return []  # no data available

    async def _verify_claim_sources(self) -> list[str]:
        """Cross-verify claim artifacts: check that source_artifact IDs exist on the board.

        Returns a list of warning strings for claims whose sources are unverifiable.
        """
        warnings: list[str] = []
        if not self._board:
            return warnings

        # Collect all artifact IDs that exist on the board
        existing_ids: set[str] = set()
        for at in ArtifactType:
            try:
                metas = await self._board.list_artifacts(at)
                for m in metas:
                    existing_ids.add(m.artifact_id)
            except Exception:
                continue

        # Check draft content for citation references against evidence artifacts
        evidence_titles: list[str] = []
        evidence_ids: list[str] = []
        try:
            evidence_metas = await self._board.list_artifacts(ArtifactType.EVIDENCE_FINDINGS)
            for m in evidence_metas:
                evidence_ids.append(m.artifact_id)
                ver = await self._board.get_latest_version(
                    ArtifactType.EVIDENCE_FINDINGS, m.artifact_id
                )
                if ver > 0:
                    from backend.types import ContextLevel

                    content = await self._board.read_artifact(
                        ArtifactType.EVIDENCE_FINDINGS,
                        m.artifact_id,
                        ver,
                        ContextLevel.L2,
                    )
                    if isinstance(content, str) and len(content) > 10:
                        evidence_titles.append(content[:200])
        except Exception as exc:
            logger.debug("[Critic] Failed to load evidence for verification: %s", exc)

        # Scan draft artifacts for unverifiable citations
        try:
            from backend.utils.verification import verify_citations

            draft_metas = await self._board.list_artifacts(ArtifactType.DRAFT)
            for m in draft_metas[-3:]:  # check last 3 drafts
                ver = await self._board.get_latest_version(ArtifactType.DRAFT, m.artifact_id)
                if ver == 0:
                    continue
                from backend.types import ContextLevel

                raw = await self._board.read_artifact(
                    ArtifactType.DRAFT, m.artifact_id, ver, ContextLevel.L2
                )
                if not raw:
                    continue
                text = raw if isinstance(raw, str) else str(raw)
                unverified = verify_citations(text, evidence_titles, evidence_ids)
                if unverified:
                    warnings.append(
                        f"Draft '{m.artifact_id}' has {len(unverified)} unverifiable "
                        f"citation(s): {', '.join(unverified[:5])}"
                    )
        except Exception as exc:
            logger.debug("[Critic] Draft citation verification failed: %s", exc)

        return warnings

    async def post_execute(
        self, response: AgentResponse, context: str, task: AgentTask
    ) -> AgentResponse:
        """Extract action items from review → auto-create InfoRequests.

        Also cross-verifies claim sources against the board to flag
        potentially hallucinated citations.

        Uses multiple extraction strategies in priority order:
        1. Structured: parse 'actionable_suggestions' from review content dict
        2. Keyword: look for role mentions + action verbs in review text
        """
        # --- Claim-source cross-verification ---
        claim_warnings = await self._verify_claim_sources()
        if claim_warnings:
            for w in claim_warnings:
                logger.warning("[Critic] Hallucination check: %s", w)
            # Inject warnings into the first review action's content
            for action in response.actions:
                if action.target == ArtifactType.REVIEW.value:
                    existing = action.content.get("hallucination_warnings", [])
                    action.content["hallucination_warnings"] = existing + claim_warnings
                    break

        if not self._info_service:
            return response

        # Role name mapping (English + Chinese) → AgentRole
        role_map: dict[str, AgentRole] = {}
        for name, role in [
            ("scientist", AgentRole.SCIENTIST), ("研究员", AgentRole.SCIENTIST),
            ("librarian", AgentRole.LIBRARIAN), ("文献员", AgentRole.LIBRARIAN),
            ("writer", AgentRole.WRITER), ("撰写员", AgentRole.WRITER),
            ("director", AgentRole.DIRECTOR), ("主管", AgentRole.DIRECTOR),
        ]:
            role_map[name] = role

        created = 0
        max_requests = 4  # cap total InfoRequests per review

        for action in response.actions:
            if action.target != ArtifactType.REVIEW.value:
                continue

            # Strategy 1: structured suggestions from content dict
            suggestions = action.content.get("actionable_suggestions", [])
            if isinstance(suggestions, list):
                for suggestion in suggestions[:max_requests]:
                    if isinstance(suggestion, dict):
                        target_str = suggestion.get("target", "").lower()
                        text = suggestion.get("action", suggestion.get("text", ""))
                    elif isinstance(suggestion, str):
                        target_str = ""
                        text = suggestion
                    else:
                        continue
                    target_role = self._resolve_target_role(target_str, text, role_map)
                    if target_role and len(str(text)) > 10 and created < max_requests:
                        try:
                            await self._info_service.create_request(
                                AgentRole.CRITIC, target_role, str(text)[:300]
                            )
                            created += 1
                        except Exception as exc:
                            logger.debug("[Critic] InfoRequest failed: %s", exc)

            if created >= max_requests:
                break

            # Strategy 2: keyword extraction from review text
            content_text = str(action.content.get("text", ""))
            if not content_text or created >= max_requests:
                continue

            # Split into sentences and look for role + action patterns
            sentences = re.split(r"[.。;；\n]", content_text)
            for sent in sentences:
                if created >= max_requests:
                    break
                sent_lower = sent.lower().strip()
                if len(sent_lower) < 15:
                    continue
                # Check if sentence mentions a role
                for name, role in role_map.items():
                    if name in sent_lower:
                        # Check for action verbs
                        if re.search(
                            r"(?:should|must|need|recommend|suggest|"
                            r"应该|需要|建议|必须)",
                            sent_lower,
                        ):
                            try:
                                await self._info_service.create_request(
                                    AgentRole.CRITIC, role, sent.strip()[:300]
                                )
                                created += 1
                            except Exception as exc:
                                logger.debug("[Critic] InfoRequest failed: %s", exc)
                            break  # one role per sentence

        return response

    @staticmethod
    def _resolve_target_role(
        target_str: str, text: str, role_map: dict[str, AgentRole]
    ) -> AgentRole | None:
        """Resolve target agent from structured field or text content."""
        combined = f"{target_str} {text}".lower()
        for name, role in role_map.items():
            if name in combined:
                return role
        return None
