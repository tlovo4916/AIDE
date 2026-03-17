"""SubAgent and SubAgentPool for parallel focused task execution."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Protocol

from backend.config import settings
from backend.protocols import Board, LLMRouter
from backend.types import AgentRole, SubAgentRequest, SubAgentResult

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 300.0  # 5 minutes
_SUBAGENT_MODEL = "deepseek-chat"


class ContextBuilder(Protocol):
    async def build(self, role: AgentRole, task: str) -> str: ...


# -----------------------------------------------------------------------
# SubAgent
# -----------------------------------------------------------------------


class SubAgent:
    """A lightweight, single-purpose agent spawned by a parent specialist.

    SubAgents build their own context (via *ContextBuilder*), cannot raise
    challenges or spawn further subagents, and write intermediate output
    to ``scratch/subagents/{id}/``.
    """

    def __init__(
        self,
        parent_role: AgentRole,
        task: str,
        tools: list[str],
        model_override: str | None,
        workspace_path: Path,
        llm_router: LLMRouter,
    ) -> None:
        self.id = f"sub-{uuid.uuid4().hex[:12]}"
        self.parent_role = parent_role
        self.task = task
        self.tools = tools
        self.model_override = model_override
        self.workspace_path = workspace_path
        self._llm_router = llm_router
        self._scratch_dir = workspace_path / "scratch" / "subagents" / self.id

    async def execute(self, context_builder: ContextBuilder, board: Board) -> SubAgentResult:
        self._scratch_dir.mkdir(parents=True, exist_ok=True)
        try:
            context = await context_builder.build(self.parent_role, self.task)
            model = self.model_override or _SUBAGENT_MODEL
            prompt = self._build_prompt(context)
            raw = await self._llm_router.generate(model, prompt)
            output = self._parse_output(raw)
            self._persist(output)
            return SubAgentResult(
                subagent_id=self.id,
                parent_role=self.parent_role,
                task=self.task,
                output=output,
                success=True,
            )
        except Exception as exc:
            logger.exception("SubAgent %s failed", self.id)
            return SubAgentResult(
                subagent_id=self.id,
                parent_role=self.parent_role,
                task=self.task,
                success=False,
                error=str(exc),
            )

    def _build_prompt(self, context: str) -> str:
        return (
            "You are a focused research sub-agent. "
            "Complete the task below and return a JSON object with keys: "
            '"findings", "summary", "references".\n\n'
            f"## Context\n\n{context}\n\n"
            f"## Task\n\n{self.task}\n\n"
            f"## Available Tools\n\n{', '.join(self.tools) or 'none'}\n"
        )

    @staticmethod
    def _parse_output(raw: str) -> dict[str, Any]:
        text = raw.strip()
        for fence in ("```json", "```"):
            idx = text.find(fence)
            if idx == -1:
                continue
            start = idx + len(fence)
            end = text.find("```", start)
            if end == -1:
                continue
            text = text[start:end].strip()
            break
        try:
            return json.loads(text)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            return {"raw_output": raw[:2000]}

    def _persist(self, output: dict[str, Any]) -> None:
        path = self._scratch_dir / "output.json"
        path.write_text(json.dumps(output, ensure_ascii=False, indent=2))


# -----------------------------------------------------------------------
# SubAgentPool
# -----------------------------------------------------------------------


class SubAgentPool:
    """Manages concurrent SubAgent execution with concurrency + timeout caps."""

    def __init__(
        self,
        llm_router: LLMRouter,
        max_concurrent: int | None = None,
    ) -> None:
        self._llm_router = llm_router
        self._max_concurrent = max_concurrent or settings.max_subagents_per_agent
        self._active: dict[str, SubAgent] = {}

    async def spawn(
        self,
        parent_role: AgentRole,
        requests: list[SubAgentRequest],
        workspace_path: Path,
        context_builder: ContextBuilder,
        board: Board,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> list[SubAgentResult]:
        if not requests:
            return []

        capped = requests[: self._max_concurrent]
        agents = [
            SubAgent(
                parent_role=parent_role,
                task=req.task,
                tools=req.tools,
                model_override=req.model_override,
                workspace_path=workspace_path,
                llm_router=self._llm_router,
            )
            for req in capped
        ]

        for a in agents:
            self._active[a.id] = a

        task_map: dict[asyncio.Task[SubAgentResult], SubAgent] = {
            asyncio.create_task(a.execute(context_builder, board)): a for a in agents
        }

        try:
            done, pending = await asyncio.wait(
                task_map.keys(),
                timeout=timeout,
                return_when=asyncio.ALL_COMPLETED,
            )

            for t in pending:
                t.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

            results: list[SubAgentResult] = []
            for t, agent in task_map.items():
                if t in done:
                    try:
                        results.append(t.result())
                    except Exception as exc:
                        results.append(
                            SubAgentResult(
                                subagent_id=agent.id,
                                parent_role=parent_role,
                                task=agent.task,
                                success=False,
                                error=str(exc),
                            )
                        )
                else:
                    results.append(
                        SubAgentResult(
                            subagent_id=agent.id,
                            parent_role=parent_role,
                            task=agent.task,
                            success=False,
                            error="timeout",
                        )
                    )
            return results
        finally:
            for a in agents:
                self._active.pop(a.id, None)

    @property
    def active_count(self) -> int:
        return len(self._active)
