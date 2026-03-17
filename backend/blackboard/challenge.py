"""Challenge manager -- structured disagreement resolution."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.types import AgentRole, ChallengeRecord, ChallengeStatus

if TYPE_CHECKING:
    from backend.blackboard.board import Blackboard


class ChallengeManager:
    async def raise_challenge(
        self,
        board: Blackboard,
        challenger: AgentRole,
        target_artifact: str,
        argument: str,
        evidence_refs: list[str] | None = None,
    ) -> ChallengeRecord:
        rec = ChallengeRecord(
            challenge_id=str(uuid.uuid4()),
            challenger=challenger,
            target_artifact=target_artifact,
            argument=argument,
            evidence_refs=evidence_refs or [],
        )
        await board.write_challenge(rec)
        return rec

    async def resolve_challenge(
        self,
        board: Blackboard,
        challenge_id: str,
        responder: AgentRole,
        response: str,
    ) -> ChallengeRecord:
        rec = await board.read_challenge(challenge_id)
        if rec is None:
            raise ValueError(f"Challenge {challenge_id} not found")
        rec.status = ChallengeStatus.RESOLVED
        rec.responder = responder
        rec.response = response
        rec.resolved_at = datetime.now(UTC)
        await board.write_challenge(rec)
        return rec

    async def dismiss_challenge(
        self,
        board: Blackboard,
        challenge_id: str,
        reason: str,
    ) -> ChallengeRecord:
        rec = await board.read_challenge(challenge_id)
        if rec is None:
            raise ValueError(f"Challenge {challenge_id} not found")
        rec.status = ChallengeStatus.DISMISSED
        rec.response = reason
        rec.resolved_at = datetime.now(UTC)
        await board.write_challenge(rec)
        return rec

    async def get_challenges(
        self,
        board: Blackboard,
        status: ChallengeStatus | None = None,
        target_artifact: str | None = None,
    ) -> list[ChallengeRecord]:
        all_challenges = await board.list_challenges()
        results: list[ChallengeRecord] = []
        for ch in all_challenges:
            if status is not None and ch.status != status:
                continue
            if target_artifact is not None and ch.target_artifact != target_artifact:
                continue
            results.append(ch)
        return results

    async def count_open_challenges(self, board: Blackboard) -> int:
        return len(await board.get_open_challenges())
