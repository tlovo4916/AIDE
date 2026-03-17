"""Writer agent -- paper composition and revision."""

from __future__ import annotations

import logging
import re

from backend.agents.base import BaseAgent
from backend.types import AgentResponse, AgentRole, AgentTask, ArtifactType

logger = logging.getLogger(__name__)


class WriterAgent(BaseAgent):
    role = AgentRole.WRITER
    system_prompt_template = "writer.j2"
    preferred_model = "deepseek-chat"
    primary_artifact_types = [
        ArtifactType.OUTLINE,
        ArtifactType.DRAFT,
    ]
    dependency_artifact_types = [
        ArtifactType.DIRECTIONS,
        ArtifactType.HYPOTHESES,
        ArtifactType.EVIDENCE_FINDINGS,
    ]
    challengeable_roles = [AgentRole.SCIENTIST]
    can_spawn_subagents = True

    async def pre_execute(self, context: str, task: AgentTask) -> str:
        """Build claim-evidence map from board artifacts with evidence counts."""
        lines = await self._build_artifact_summary(
            [
                (ArtifactType.EVIDENCE_FINDINGS, "Evidence artifacts"),
                (ArtifactType.HYPOTHESES, "Hypotheses"),
                (ArtifactType.DRAFT, "Drafts"),
                (ArtifactType.OUTLINE, "Outlines"),
            ],
            "Claim-Evidence Map",
        )

        # Query board for artifacts needed by downstream analysis
        evidence = await self._query_board(ArtifactType.EVIDENCE_FINDINGS)
        hypotheses = await self._query_board(ArtifactType.HYPOTHESES)
        drafts = await self._query_board(ArtifactType.DRAFT)

        if lines:
            evidence_count = len(evidence) + len(hypotheses)
            lines.append(f"  evidence_count: {evidence_count} distinct source artifacts")

            # Count citations in existing drafts
            citation_pattern = re.compile(
                r"\[(?:\d+|[A-Z][a-z]+(?:\s+et\s+al\.?)?,?\s*\d{4})\]"
            )
            total_citations = 0
            total_claims = 0
            for d in drafts[-2:]:
                text = d if isinstance(d, str) else str(d)
                total_citations += len(citation_pattern.findall(text))
                total_claims += len(re.findall(
                    r"(?:studies? show|research indicates?|evidence suggests?|"
                    r"研究表明|证据显示)",
                    text,
                    re.I,
                ))

            if total_claims or total_citations:
                lines.append(
                    f"  Draft analysis: {total_claims} claims, "
                    f"{total_citations} citations"
                )
                if total_claims > 0 and total_citations == 0:
                    lines.append("  ⚠️ Claims exist but no citations found")

        # Fallback: regex scan context
        if not lines:
            claim_pattern = re.compile(
                r"(?:(?:studies? show|research indicates?|evidence suggests?|"
                r"it (?:has been |is )(?:shown|demonstrated|found)|"
                r"研究表明|证据显示|已有研究).*?)(?:\.|。)",
                re.I,
            )
            claims = claim_pattern.findall(context)
            if claims:
                lines = ["\n## Claim-Evidence Map (from context)"]
                citation_pattern = re.compile(
                    r"\[(?:\d+|[A-Z][a-z]+(?:\s+et\s+al\.?)?,?\s*\d{4})\]"
                )
                cited_count = sum(
                    1 for c in claims[:15] if citation_pattern.search(c.strip())
                )
                uncited_count = min(len(claims), 15) - cited_count
                lines.append(f"  {cited_count} cited, {uncited_count} uncited claims")

        # Verify citations in recent drafts against known evidence artifacts
        if drafts and evidence:
            from backend.types import ContextLevel
            from backend.utils.verification import verify_citations

            known_titles: list[str] = []
            known_ids: list[str] = []
            for e in evidence:
                aid = e.artifact_id if hasattr(e, "artifact_id") else str(e)
                known_ids.append(aid)
                if hasattr(e, "artifact_id") and self._board:
                    try:
                        ver = await self._board.get_latest_version(
                            ArtifactType.EVIDENCE_FINDINGS, e.artifact_id
                        )
                        if ver > 0:
                            content = await self._board.read_artifact(
                                ArtifactType.EVIDENCE_FINDINGS,
                                e.artifact_id,
                                ver,
                                ContextLevel.L2,
                            )
                            if isinstance(content, str) and len(content) > 10:
                                known_titles.append(content[:200])
                    except Exception:
                        pass

            for d in drafts[-2:]:
                draft_text = d if isinstance(d, str) else str(d)
                unverified = verify_citations(draft_text, known_titles, known_ids)
                if unverified:
                    lines.append(
                        f"  ⚠️ {len(unverified)} unverifiable citation(s) in draft: "
                        f"{', '.join(unverified[:5])}"
                    )
                    logger.warning(
                        "[Writer] Pre-hook: %d unverifiable citations detected",
                        len(unverified),
                    )

        if lines:
            return context + "\n" + "\n".join(lines)
        return context

    async def post_execute(
        self, response: AgentResponse, context: str, task: AgentTask
    ) -> AgentResponse:
        """Request citations from Librarian when draft has uncited claims."""
        for action in response.actions:
            if action.target != ArtifactType.DRAFT.value:
                continue
            content_text = str(action.content.get("text", ""))
            if len(content_text) < 100:
                continue

            # Count claim-like sentences vs citations in output
            claim_sents = len(re.findall(
                r"(?:studies? show|research indicates?|evidence suggests?|"
                r"研究表明|证据显示)",
                content_text,
                re.I,
            ))
            cite_count = len(re.findall(
                r"\[(?:\d+|[A-Z][a-z]+(?:\s+et\s+al\.?)?,?\s*\d{4})\]",
                content_text,
            ))
            if claim_sents > 0 and cite_count == 0 and self._info_service:
                logger.info(
                    "[Writer] Post-hook: draft has %d uncited claims, "
                    "requesting citations from Librarian",
                    claim_sents,
                )
                try:
                    await self._info_service.create_request(
                        AgentRole.WRITER,
                        AgentRole.LIBRARIAN,
                        f"Draft contains {claim_sents} claim-like sentences "
                        f"without citations. Please provide supporting "
                        f"references for these claims.",
                    )
                except Exception as exc:
                    logger.debug("[Writer] InfoRequest creation failed: %s", exc)

        return response
