"""Action executor -- dispatches BlackboardActions to board methods."""

from __future__ import annotations

import json
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
        ArtifactType.TREND_SIGNALS,
    },
    AgentRole.LIBRARIAN: {ArtifactType.EVIDENCE_FINDINGS, ArtifactType.EVIDENCE_GAPS},
    AgentRole.WRITER: {ArtifactType.OUTLINE, ArtifactType.DRAFT},
    AgentRole.CRITIC: {ArtifactType.REVIEW},
    AgentRole.SYNTHESIZER: {ArtifactType.DRAFT, ArtifactType.OUTLINE},
}

# Strict allowed types per role — used for runtime correction (narrower than WRITE_PERMISSIONS)
_ROLE_ALLOWED_TYPES: dict[AgentRole, set[ArtifactType]] = {
    AgentRole.DIRECTOR: {ArtifactType.DIRECTIONS},
    AgentRole.SCIENTIST: {
        ArtifactType.HYPOTHESES,
        ArtifactType.EVIDENCE_GAPS,
        ArtifactType.EXPERIMENT_GUIDE,
    },
    AgentRole.LIBRARIAN: {ArtifactType.EVIDENCE_FINDINGS, ArtifactType.TREND_SIGNALS},
    AgentRole.WRITER: {ArtifactType.OUTLINE, ArtifactType.DRAFT},
    AgentRole.CRITIC: {ArtifactType.REVIEW},
    AgentRole.SYNTHESIZER: {ArtifactType.DRAFT},
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
            ActionType.SPAWN_SUBAGENT: self._exec_spawn_subagent,
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
            target_type = ArtifactType(action.content.get("artifact_type", action.target))
        except ValueError:
            return
        allowed = WRITE_PERMISSIONS.get(action.agent_role, set())
        if target_type not in allowed:
            raise PermissionError(f"{action.agent_role.value} cannot write {target_type.value}")

    @staticmethod
    def _is_content_empty(content: dict) -> bool:
        """Return True if the content dict has no meaningful data."""
        skip_keys = {"artifact_type", "artifact_id", "version", "tags", "agent_role"}
        for k, v in content.items():
            if k in skip_keys:
                continue
            if isinstance(v, str) and v.strip():
                return False
            if isinstance(v, (int, float)) and v != 0:
                return False
            if isinstance(v, (list, dict)) and v:
                return False
        return True

    @staticmethod
    async def _exec_write_artifact(action: BlackboardAction, board: Blackboard) -> None:
        c = action.content
        if ActionExecutor._is_content_empty(c):
            logger.warning(
                "Rejecting empty artifact from %s: %s",
                action.agent_role.value,
                {k: type(v).__name__ for k, v in c.items()},
            )
            return
        role_default: dict[AgentRole, ArtifactType] = {
            AgentRole.DIRECTOR: ArtifactType.DIRECTIONS,
            AgentRole.SCIENTIST: ArtifactType.HYPOTHESES,
            AgentRole.LIBRARIAN: ArtifactType.EVIDENCE_FINDINGS,
            AgentRole.WRITER: ArtifactType.OUTLINE,
            AgentRole.CRITIC: ArtifactType.REVIEW,
            AgentRole.SYNTHESIZER: ArtifactType.DRAFT,
        }
        raw_type = c.get("artifact_type", action.target)
        try:
            artifact_type = ArtifactType(raw_type)
        except ValueError:
            artifact_type = role_default.get(action.agent_role, ArtifactType.EVIDENCE_FINDINGS)
            logger.warning(
                "_exec_write_artifact: invalid artifact_type %r from %s, falling back to %s",
                raw_type,
                action.agent_role.value,
                artifact_type.value,
            )

        # --- Layer 3: enforce per-role artifact_type whitelist ---
        allowed = _ROLE_ALLOWED_TYPES.get(action.agent_role)
        if allowed and artifact_type not in allowed:
            corrected = role_default.get(action.agent_role, artifact_type)
            logger.warning(
                "_exec_write_artifact: %s tried to write %r, corrected to %r"
                " (not in allowed: %s)",
                action.agent_role.value,
                artifact_type.value,
                corrected.value,
                [a.value for a in allowed],
            )
            artifact_type = corrected

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
            content_l2=c.get("content_l2") or json.dumps(c, ensure_ascii=False),
            meta=meta,
        )

    @staticmethod
    async def _exec_post_message(action: BlackboardAction, board: Blackboard) -> None:
        c = action.content
        to_agent = None
        if c.get("to_agent"):
            try:
                to_agent = AgentRole(c["to_agent"])
            except ValueError:
                logger.warning(
                    "_exec_post_message: invalid to_agent %r, ignoring",
                    c["to_agent"],
                )
        # LLM may use "text", "content", or "message" for the body
        text = c.get("text") or c.get("content") or c.get("message") or ""
        if isinstance(text, dict):
            text = json.dumps(text, ensure_ascii=False)
        elif not isinstance(text, str):
            text = str(text)
        # Ensure refs is a list of strings
        refs = c.get("refs", [])
        if not isinstance(refs, list):
            refs = [str(refs)] if refs else []
        else:
            refs = [str(r) for r in refs]
        try:
            msg = Message(
                message_id=c.get("message_id", str(uuid.uuid4())),
                from_agent=action.agent_role,
                to_agent=to_agent,
                content=text[:5000],  # prevent excessively long messages
                refs=refs,
            )
            await board.post_message(msg)
        except Exception as exc:
            logger.warning(
                "_exec_post_message: validation failed for %s: %s",
                action.agent_role.value,
                exc,
            )

    @staticmethod
    async def _exec_raise_challenge(action: BlackboardAction, board: Blackboard) -> None:
        c = action.content
        argument = c.get("argument", "").strip()
        if not argument:
            logger.warning("Rejecting empty challenge from %s", action.agent_role.value)
            return
        rec = ChallengeRecord(
            challenge_id=c.get("challenge_id", str(uuid.uuid4())),
            challenger=action.agent_role,
            target_artifact=c.get("target_artifact", action.target),
            argument=argument,
            evidence_refs=c.get("evidence_refs", []),
        )
        await board.write_challenge(rec)

    @staticmethod
    async def _exec_resolve_challenge(action: BlackboardAction, board: Blackboard) -> None:
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
    async def _exec_request_info(action: BlackboardAction, board: Blackboard) -> None:
        msg = Message(
            message_id=str(uuid.uuid4()),
            from_agent=action.agent_role,
            content=f"[INFO REQUEST] {action.content.get('query', '')}",
            refs=action.content.get("refs", []),
        )
        await board.post_message(msg)

    @staticmethod
    async def _exec_spawn_subagent(action: BlackboardAction, board: Blackboard) -> None:
        """Record spawn_subagent requests as messages.

        Actual subagent spawning is handled by the engine's SubAgentPool;
        here we just log the request so it's visible on the blackboard.
        """
        c = action.content
        msg = Message(
            message_id=str(uuid.uuid4()),
            from_agent=action.agent_role,
            content=(
                f"[SUBAGENT REQUEST] role={c.get('role', '?')} "
                f"task={c.get('task', c.get('description', ''))[:200]}"
            ),
            refs=c.get("refs", []),
        )
        await board.post_message(msg)

    @staticmethod
    async def _log_as_decision(action: BlackboardAction, board: Blackboard) -> None:
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
            rationale=action.rationale
            or (f"{action.agent_role.value} performed {action.action_type.value}"),
            decided_by=action.agent_role,
        )
        await board.write_decision(decision)
