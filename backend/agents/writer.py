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
        """Build claim-evidence map from board artifacts."""
        lines: list[str] = []

        # Query board for evidence and draft artifacts
        if self._board:
            try:
                evidence = await self._board.list_artifacts(ArtifactType.EVIDENCE_FINDINGS)
                hypotheses = await self._board.list_artifacts(ArtifactType.HYPOTHESES)
                drafts = await self._board.list_artifacts(ArtifactType.DRAFT)
                outlines = await self._board.list_artifacts(ArtifactType.OUTLINE)

                lines.append("\n## Claim-Evidence Map (from board)")
                lines.append(f"  Evidence artifacts: {len(evidence)}")
                lines.append(f"  Hypotheses: {len(hypotheses)}")
                lines.append(f"  Drafts: {len(drafts)}, Outlines: {len(outlines)}")

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
            except Exception as exc:
                logger.debug("[Writer] Board query failed: %s", exc)

        # Fallback: regex scan context
        if len(lines) <= 1:
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
