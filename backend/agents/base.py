"""Base agent class for all AIDE specialist agents."""

from __future__ import annotations

import json
import logging
from abc import ABC
from pathlib import Path
from typing import Protocol, runtime_checkable

import jinja2

from backend.types import (
    AgentResponse,
    AgentRole,
    AgentTask,
    ArtifactType,
    BlackboardAction,
)

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


@runtime_checkable
class LLMRouter(Protocol):
    """Structural interface for the LLM routing layer."""

    async def generate(
        self, model: str, prompt: str, *, system_prompt: str | None = None
    ) -> str: ...


@runtime_checkable
class WriteBackGuard(Protocol):
    """Structural interface for blackboard write-back validation."""

    async def check(
        self, agent_response: str, executed_actions: list[BlackboardAction]
    ) -> list[BlackboardAction]: ...


class BaseAgent(ABC):
    """Abstract base for every specialist agent in AIDE.

    Subclasses set the class-level configuration attributes; the runtime
    behaviour (prompt building, LLM call, response parsing, write-back
    validation) is handled here.
    """

    role: AgentRole
    system_prompt_template: str
    preferred_model: str
    primary_artifact_types: list[ArtifactType]
    dependency_artifact_types: list[ArtifactType]
    challengeable_roles: list[AgentRole]
    can_spawn_subagents: bool

    def __init__(
        self,
        llm_router: LLMRouter,
        write_back_guard: WriteBackGuard,
        research_topic: str = "",
        project_id: str = "",
    ) -> None:
        self._llm_router = llm_router
        self._write_back_guard = write_back_guard
        self._research_topic = research_topic
        self._project_id = project_id
        self._jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(_PROMPTS_DIR)),
            autoescape=False,
            undefined=jinja2.StrictUndefined,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _resolve_model(self) -> str:
        """Return the model to use, respecting user overrides via settings."""
        from backend.config import settings
        overrides = settings.agent_model_overrides
        role_key = self.role.value
        if overrides and role_key in overrides and overrides[role_key]:
            return overrides[role_key]
        return self.preferred_model

    async def execute(self, context: str, task: AgentTask) -> AgentResponse:
        prompt = self._build_prompt(context, task)
        model = self._resolve_model()
        raw = await self._llm_router.generate(model, prompt)

        response = self._parse_response(raw)

        for action in response.actions:
            action.agent_role = self.role

        extra_actions = await self._write_back_guard.check(raw, response.actions)
        response.actions.extend(extra_actions)

        if not self.can_spawn_subagents:
            response.subagent_requests = []

        return response

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _load_prompt_template(self) -> jinja2.Template:
        return self._jinja_env.get_template(self.system_prompt_template)

    def _build_prompt(self, context: str, task: AgentTask) -> str:
        template = self._load_prompt_template()
        # Extract trend signals from context if present
        trend_signals = ""
        trend_marker = "## Trend Signals"
        if trend_marker in context:
            idx = context.index(trend_marker)
            # Find the next ## heading or end of string
            end_idx = context.find("\n## ", idx + len(trend_marker))
            trend_signals = context[idx:end_idx].strip() if end_idx != -1 else context[idx:].strip()

        return template.render(
            role=self.role.value,
            primary_artifacts=[a.value for a in self.primary_artifact_types],
            dependency_artifacts=[a.value for a in self.dependency_artifact_types],
            can_spawn=self.can_spawn_subagents,
            research_topic=self._research_topic,
            trend_signals=trend_signals,
            context=context,
            task=format_task(task),
        )

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_response(self, raw: str) -> AgentResponse:
        text = extract_json_block(raw)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning(
                "Agent %s: non-JSON response, wrapping as summary",
                self.role.value,
            )
            return AgentResponse(reasoning_summary=raw[:500])

        for action in data.get("actions", []):
            action.setdefault("agent_role", self.role.value)
            # LLM 有时将 content 返回为字符串而非 dict，自动修正
            if isinstance(action.get("content"), str):
                action["content"] = {"text": action["content"]}
            elif not isinstance(action.get("content"), dict):
                action["content"] = {}

        try:
            return AgentResponse.model_validate(data)
        except Exception as exc:
            logger.warning(
                "Agent %s: AgentResponse validation failed (%s), returning summary",
                self.role.value, exc,
            )
            return AgentResponse(reasoning_summary=raw[:500])


# ------------------------------------------------------------------
# Utility helpers
# ------------------------------------------------------------------


def format_task(task: AgentTask) -> str:
    lines = [
        f"ID: {task.task_id}",
        f"Description: {task.description}",
        f"Priority: {task.priority.value}",
    ]
    if task.target_artifacts:
        lines.append(f"Target Artifacts: {', '.join(task.target_artifacts)}")
    if task.constraints:
        lines.append(f"Constraints: {', '.join(task.constraints)}")
    if task.allow_subagents:
        lines.append("SubAgent spawning: allowed")
    return "\n".join(lines)


def extract_json_block(text: str) -> str:
    """Pull JSON from optional markdown code fences."""
    text = text.strip()
    for fence in ("```json", "```"):
        idx = text.find(fence)
        if idx == -1:
            continue
        start = idx + len(fence)
        end = text.find("```", start)
        if end == -1:
            continue
        return text[start:end].strip()
    return text
