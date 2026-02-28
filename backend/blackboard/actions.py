"""Action executor -- dispatches BlackboardActions to board methods."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from backend.types import (
    ActionType,
    AgentRole,
    ArtifactMeta,
    ArtifactType,
    BlackboardAction,
    ChallengeRecord,
    ChallengeStatus,
    DecisionRecord,
    Message,
    ResearchPhase,
)

if TYPE_CHECKING:
    from backend.blackboard.board import Blackboard

logger = logging.getLogger(__name__)

WRITE_PERMISSIONS: dict[AgentRole, set[ArtifactType]] = {
    AgentRole.DIRECTOR: {ArtifactType.DIRECTIONS, ArtifactType.EXPERIMENT_GUIDE},
    AgentRole.SCIENTIST: {
        ArtifactType.HYPOTHESES,
        ArtifactType.EVIDENCE_FINDINGS,
        ArtifactType.EVIDENCE_GAPS,
        ArtifactType.EXPERIMENT_GUIDE,
    },
    AgentRole.LIBRARIAN: {ArtifactType.EVIDENCE_FINDINGS, ArtifactType.EVIDENCE_GAPS},
    AgentRole.WRITER: {ArtifactType.OUTLINE, ArtifactType.DRAFT},
    AgentRole.CRITIC: {ArtifactType.REVIEW},
}


class ActionExecutor:

    async def execute(self, action: BlackboardAction, board: Blackboard) -> None:
        self._validate_permissions(action)

        handlers = {
            ActionType.WRITE_ARTIFACT: self._exec_write_artifact,
            ActionType.POST_MESSAGE: self._exec_post_message,
            ActionType.RAISE_CHALLENGE: self._exec_raise_challenge,
            ActionType.RESOLVE_CHALLENGE: self._exec_resolve_challenge,
            ActionType.REQUEST_INFO: self._exec_request_info,
        }

        handler = handlers.get(action.action_type)
        if handler is None:
            logger.warning("Unhandled action type: %s", action.action_type)
            return

        await handler(action, board)

        if action.action_type in {
            ActionType.WRITE_ARTIFACT,
            ActionType.RAISE_CHALLENGE,
            ActionType.RESOLVE_CHALLENGE,
        }:
            await self._log_as_decision(action, board)

    # ------------------------------------------------------------------

    @staticmethod
    def _validate_permissions(action: BlackboardAction) -> None:
        if action.action_type != ActionType.WRITE_ARTIFACT:
            return
        try:
            target_type = ArtifactType(
                action.content.get("artifact_type", action.target)
            )
        except ValueError:
            return
        allowed = WRITE_PERMISSIONS.get(action.agent_role, set())
        if target_type not in allowed:
            raise PermissionError(
                f"{action.agent_role.value} cannot write {target_type.value}"
            )

    @staticmethod
    async def _exec_write_artifact(
        action: BlackboardAction, board: Blackboard
    ) -> None:
        c = action.content
        artifact_type = ArtifactType(c.get("artifact_type", action.target))
        artifact_id = c.get("artifact_id", str(uuid.uuid4()))
        version = c.get(
            "version",
            await board.get_latest_version(artifact_type, artifact_id) + 1,
        )
        meta = ArtifactMeta(
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            version=version,
            created_by=action.agent_role,
            tags=c.get("tags", []),
        )
        await board.write_artifact(
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            version=version,
            content_l2=c.get("content_l2", ""),
            meta=meta,
        )

    @staticmethod
    async def _exec_post_message(
        action: BlackboardAction, board: Blackboard
    ) -> None:
        c = action.content
        to_agent = AgentRole(c["to_agent"]) if c.get("to_agent") else None
        msg = Message(
            message_id=c.get("message_id", str(uuid.uuid4())),
            from_agent=action.agent_role,
            to_agent=to_agent,
            content=c.get("text", ""),
            refs=c.get("refs", []),
        )
        await board.post_message(msg)

    @staticmethod
    async def _exec_raise_challenge(
        action: BlackboardAction, board: Blackboard
    ) -> None:
        c = action.content
        rec = ChallengeRecord(
            challenge_id=c.get("challenge_id", str(uuid.uuid4())),
            challenger=action.agent_role,
            target_artifact=c.get("target_artifact", action.target),
            argument=c.get("argument", ""),
            evidence_refs=c.get("evidence_refs", []),
        )
        await board.write_challenge(rec)

    @staticmethod
    async def _exec_resolve_challenge(
        action: BlackboardAction, board: Blackboard
    ) -> None:
        c = action.content
        challenge_id = c.get("challenge_id", action.target)
        existing = await board.read_challenge(challenge_id)
        if existing is None:
            logger.warning("Challenge %s not found", challenge_id)
            return
        existing.status = ChallengeStatus.RESOLVED
        existing.responder = action.agent_role
        existing.response = c.get("response", "")
        existing.resolved_at = datetime.utcnow()
        await board.write_challenge(existing)

    @staticmethod
    async def _exec_request_info(
        action: BlackboardAction, board: Blackboard
    ) -> None:
        msg = Message(
            message_id=str(uuid.uuid4()),
            from_agent=action.agent_role,
            content=f"[INFO REQUEST] {action.content.get('query', '')}",
            refs=action.content.get("refs", []),
        )
        await board.post_message(msg)

    @staticmethod
    async def _log_as_decision(
        action: BlackboardAction, board: Blackboard
    ) -> None:
        meta = await board.get_project_meta()
        phase_str = meta.get("phase", "explore")
        try:
            phase = ResearchPhase(phase_str)
        except ValueError:
            phase = ResearchPhase.EXPLORE

        decision = DecisionRecord(
            decision_id=str(uuid.uuid4()),
            phase=phase,
            context_summary=f"Auto-logged from {action.action_type.value}",
            options=[action.action_type.value],
            chosen=action.action_type.value,
            rationale=action.rationale or (
                f"{action.agent_role.value} performed {action.action_type.value}"
            ),
            decided_by=action.agent_role,
        )
        await board.write_decision(decision)
