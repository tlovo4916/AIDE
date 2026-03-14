"""Tests for _ROLE_ALLOWED_TYPES whitelist logic in ActionExecutor.

Verifies that ActionExecutor._exec_write_artifact corrects artifact_type
when a role writes an artifact type outside its allowed whitelist.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.blackboard.actions import ActionExecutor
from backend.types import (
    ActionType,
    AgentRole,
    ArtifactType,
    BlackboardAction,
)


def _make_action(
    role: AgentRole,
    artifact_type: str,
    content_text: str = "Some meaningful content for testing purposes.",
) -> BlackboardAction:
    """Helper to build a WRITE_ARTIFACT action."""
    return BlackboardAction(
        agent_role=role,
        action_type=ActionType.WRITE_ARTIFACT,
        target=artifact_type,
        content={
            "artifact_type": artifact_type,
            "content_l2": content_text,
        },
        rationale="test",
    )


def _make_mock_board() -> MagicMock:
    """Create a mock Blackboard with required async methods."""
    board = MagicMock()
    board.get_latest_version = AsyncMock(return_value=0)
    board.write_artifact = AsyncMock()
    board.post_message = AsyncMock()
    board.write_challenge = AsyncMock()
    board.write_decision = AsyncMock()
    board.get_project_meta = AsyncMock(return_value={"phase": "explore"})
    return board


class TestRoleAllowedTypes:
    """Test the _ROLE_ALLOWED_TYPES whitelist correction logic."""

    @pytest.fixture
    def executor(self) -> ActionExecutor:
        return ActionExecutor()

    @pytest.fixture
    def board(self) -> MagicMock:
        return _make_mock_board()

    @pytest.mark.asyncio
    async def test_scientist_evidence_findings_corrected_to_hypotheses(
        self, executor: ActionExecutor, board: MagicMock
    ) -> None:
        """SCIENTIST writing 'evidence_findings' should be corrected to 'hypotheses'.

        'evidence_findings' passes WRITE_PERMISSIONS for SCIENTIST but is NOT
        in the stricter _ROLE_ALLOWED_TYPES whitelist, so it gets corrected
        to the role default ('hypotheses').
        """
        action = _make_action(AgentRole.SCIENTIST, "evidence_findings")
        await executor.execute(action, board)

        board.write_artifact.assert_called_once()
        call_kwargs = board.write_artifact.call_args
        # artifact_type is passed as keyword arg
        written_type = call_kwargs.kwargs.get(
            "artifact_type", call_kwargs.args[0] if call_kwargs.args else None
        )
        assert written_type == ArtifactType.HYPOTHESES, (
            f"Expected HYPOTHESES but got {written_type}"
        )

    @pytest.mark.asyncio
    async def test_scientist_hypotheses_passes_without_correction(
        self, executor: ActionExecutor, board: MagicMock
    ) -> None:
        """SCIENTIST writing 'hypotheses' should pass through unchanged."""
        action = _make_action(AgentRole.SCIENTIST, "hypotheses")
        await executor.execute(action, board)

        board.write_artifact.assert_called_once()
        call_kwargs = board.write_artifact.call_args
        written_type = call_kwargs.kwargs.get(
            "artifact_type", call_kwargs.args[0] if call_kwargs.args else None
        )
        assert written_type == ArtifactType.HYPOTHESES, (
            f"Expected HYPOTHESES but got {written_type}"
        )

    @pytest.mark.asyncio
    async def test_director_directions_passes_without_correction(
        self, executor: ActionExecutor, board: MagicMock
    ) -> None:
        """DIRECTOR writing 'directions' should pass through unchanged."""
        action = _make_action(AgentRole.DIRECTOR, "directions")
        await executor.execute(action, board)

        board.write_artifact.assert_called_once()
        call_kwargs = board.write_artifact.call_args
        written_type = call_kwargs.kwargs.get(
            "artifact_type", call_kwargs.args[0] if call_kwargs.args else None
        )
        assert written_type == ArtifactType.DIRECTIONS, (
            f"Expected DIRECTIONS but got {written_type}"
        )

    @pytest.mark.asyncio
    async def test_writer_draft_passes_without_correction(
        self, executor: ActionExecutor, board: MagicMock
    ) -> None:
        """WRITER writing 'draft' should pass through unchanged."""
        action = _make_action(AgentRole.WRITER, "draft")
        await executor.execute(action, board)

        board.write_artifact.assert_called_once()
        call_kwargs = board.write_artifact.call_args
        written_type = call_kwargs.kwargs.get(
            "artifact_type", call_kwargs.args[0] if call_kwargs.args else None
        )
        assert written_type == ArtifactType.DRAFT, (
            f"Expected DRAFT but got {written_type}"
        )

    @pytest.mark.asyncio
    async def test_librarian_evidence_findings_passes_without_correction(
        self, executor: ActionExecutor, board: MagicMock
    ) -> None:
        """LIBRARIAN writing 'evidence_findings' should pass through unchanged."""
        action = _make_action(AgentRole.LIBRARIAN, "evidence_findings")
        await executor.execute(action, board)

        board.write_artifact.assert_called_once()
        call_kwargs = board.write_artifact.call_args
        written_type = call_kwargs.kwargs.get(
            "artifact_type", call_kwargs.args[0] if call_kwargs.args else None
        )
        assert written_type == ArtifactType.EVIDENCE_FINDINGS, (
            f"Expected EVIDENCE_FINDINGS but got {written_type}"
        )

    @pytest.mark.asyncio
    async def test_critic_review_passes_without_correction(
        self, executor: ActionExecutor, board: MagicMock
    ) -> None:
        """CRITIC writing 'review' should pass through unchanged."""
        action = _make_action(AgentRole.CRITIC, "review")
        await executor.execute(action, board)

        board.write_artifact.assert_called_once()
        call_kwargs = board.write_artifact.call_args
        written_type = call_kwargs.kwargs.get(
            "artifact_type", call_kwargs.args[0] if call_kwargs.args else None
        )
        assert written_type == ArtifactType.REVIEW, (
            f"Expected REVIEW but got {written_type}"
        )

    @pytest.mark.asyncio
    async def test_librarian_evidence_gaps_corrected_to_evidence_findings(
        self, executor: ActionExecutor, board: MagicMock
    ) -> None:
        """LIBRARIAN writing 'evidence_gaps' should be corrected.

        'evidence_gaps' passes WRITE_PERMISSIONS for LIBRARIAN but is NOT
        in _ROLE_ALLOWED_TYPES {EVIDENCE_FINDINGS, TREND_SIGNALS}, so it
        gets corrected to LIBRARIAN's role_default: EVIDENCE_FINDINGS.
        """
        action = _make_action(AgentRole.LIBRARIAN, "evidence_gaps")
        await executor.execute(action, board)

        board.write_artifact.assert_called_once()
        call_kwargs = board.write_artifact.call_args
        written_type = call_kwargs.kwargs.get(
            "artifact_type", call_kwargs.args[0] if call_kwargs.args else None
        )
        assert written_type == ArtifactType.EVIDENCE_FINDINGS, (
            f"Expected EVIDENCE_FINDINGS (corrected) but got {written_type}"
        )

    @pytest.mark.asyncio
    async def test_writer_outline_passes_without_correction(
        self, executor: ActionExecutor, board: MagicMock
    ) -> None:
        """WRITER writing 'outline' should pass through (in allowed set)."""
        action = _make_action(AgentRole.WRITER, "outline")
        await executor.execute(action, board)

        board.write_artifact.assert_called_once()
        call_kwargs = board.write_artifact.call_args
        written_type = call_kwargs.kwargs.get(
            "artifact_type", call_kwargs.args[0] if call_kwargs.args else None
        )
        assert written_type == ArtifactType.OUTLINE, (
            f"Expected OUTLINE but got {written_type}"
        )
