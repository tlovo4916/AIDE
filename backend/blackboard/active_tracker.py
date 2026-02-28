"""Active tracker -- monitors artifact access frequency."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.types import ArtifactMeta, ArtifactType

if TYPE_CHECKING:
    from backend.blackboard.board import Blackboard


class ActiveTracker:

    async def increment(
        self,
        board: Blackboard,
        artifact_type: ArtifactType,
        artifact_id: str,
    ) -> None:
        meta = await board.read_artifact_meta(artifact_type, artifact_id)
        if meta is None:
            return
        await board.update_artifact_meta(
            artifact_type,
            artifact_id,
            active_count=meta.active_count + 1,
        )

    async def get_top_active(
        self,
        board: Blackboard,
        artifact_type: ArtifactType,
        top_k: int = 10,
    ) -> list[ArtifactMeta]:
        all_metas = await board.list_artifacts(artifact_type)
        sorted_metas = sorted(
            all_metas, key=lambda m: m.active_count, reverse=True,
        )
        return sorted_metas[:top_k]

    async def get_cold_artifacts(
        self,
        board: Blackboard,
        artifact_type: ArtifactType,
        threshold: int = 3,
    ) -> list[ArtifactMeta]:
        all_metas = await board.list_artifacts(artifact_type)
        return [m for m in all_metas if m.active_count < threshold]
