"""LLM Router -- dispatches calls to the right provider with fallback."""

from __future__ import annotations

import logging
from typing import Any

from backend.config import settings
from backend.types import AgentRole
from backend.llm.models import LLMResponse
from backend.llm.providers.deepseek import DeepSeekProvider
from backend.llm.providers.openrouter import OpenRouterProvider
from backend.llm.tracker import TokenTracker

log = logging.getLogger(__name__)

DEFAULT_AGENT_MODEL: dict[AgentRole, str] = {
    AgentRole.DIRECTOR: "deepseek-reasoner",
    AgentRole.SCIENTIST: "deepseek-reasoner",
    AgentRole.LIBRARIAN: "deepseek-reasoner",
    AgentRole.WRITER: "deepseek-reasoner",
    AgentRole.CRITIC: "deepseek-reasoner",
}

DEEPSEEK_MODELS = {"deepseek-chat", "deepseek-reasoner"}

FALLBACK_CHAIN: list[str] = ["deepseek-chat", "deepseek-reasoner"]


class LLMRouter:

    def __init__(
        self,
        deepseek: DeepSeekProvider | None = None,
        openrouter: OpenRouterProvider | None = None,
        tracker: TokenTracker | None = None,
    ) -> None:
        self._deepseek = deepseek or DeepSeekProvider()
        self._openrouter = openrouter or OpenRouterProvider()
        self._tracker = tracker

    async def close(self) -> None:
        await self._deepseek.close()
        await self._openrouter.close()

    def _is_deepseek(self, model: str) -> bool:
        return model in DEEPSEEK_MODELS or model.startswith("deepseek")

    def resolve_model(self, role: AgentRole | str | None = None) -> str:
        """Return the model string for a given agent role, respecting user overrides."""
        overrides = settings.agent_model_overrides
        if role is not None:
            key = role.value if isinstance(role, AgentRole) else role
            if overrides and key in overrides and overrides[key]:
                return overrides[key]
            if isinstance(role, AgentRole):
                return DEFAULT_AGENT_MODEL.get(role, settings.default_model)
        return settings.default_model

    # ------------------------------------------------------------------
    # generate() -- simple text-in / text-out interface used by agents
    # ------------------------------------------------------------------

    async def generate(
        self,
        model: str,
        prompt: str,
        *,
        system_prompt: str | None = None,
        project_id: str | None = None,
        agent_role: AgentRole | None = None,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self.call(
            messages=messages,
            model=model,
            project_id=project_id,
            agent_role=agent_role,
        )
        return response.content

    # ------------------------------------------------------------------
    # call() -- full LLMResponse interface with fallback chain
    # ------------------------------------------------------------------

    async def call(
        self,
        messages: list[dict[str, str]],
        model: str,
        project_id: str | None = None,
        agent_role: AgentRole | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        errors: list[str] = []

        models_to_try = [model] + [m for m in FALLBACK_CHAIN if m != model]
        log.info("LLMRouter.call: model=%s, role=%s, fallback=%s", model, agent_role, models_to_try)

        for m in models_to_try:
            try:
                if self._is_deepseek(m):
                    response = await self._deepseek.call(messages, model=m, **kwargs)
                else:
                    response = await self._openrouter.call(messages, model=m, **kwargs)

                if self._tracker and project_id and agent_role:
                    await self._tracker.record_usage(
                        project_id=project_id,
                        agent_role=agent_role,
                        model=response.model or m,
                        prompt_tokens=response.prompt_tokens,
                        completion_tokens=response.completion_tokens,
                    )

                return response
            except Exception as exc:
                log.warning("Provider call failed for model=%s: %s", m, exc)
                errors.append(f"{m}: {exc}")

        raise RuntimeError(
            f"All LLM providers failed. Errors: {'; '.join(errors)}"
        )

    async def call_for_agent(
        self,
        agent_role: AgentRole,
        messages: list[dict[str, str]],
        project_id: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        preferred = self.resolve_model(agent_role)
        return await self.call(
            messages=messages,
            model=preferred,
            project_id=project_id,
            agent_role=agent_role,
            **kwargs,
        )
