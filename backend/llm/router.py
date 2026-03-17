"""LLM Router -- dispatches calls to the right provider with fallback."""

from __future__ import annotations

import logging
from typing import Any

from backend.config import settings
from backend.llm.models import LLMResponse
from backend.llm.providers.anthropic import AnthropicProvider
from backend.llm.providers.deepseek import DeepSeekProvider
from backend.llm.providers.openrouter import OpenRouterProvider
from backend.llm.tracker import TokenTracker
from backend.types import AgentRole

log = logging.getLogger(__name__)

DEFAULT_AGENT_MODEL: dict[AgentRole, str] = {
    AgentRole.DIRECTOR: "deepseek-reasoner",
    AgentRole.SCIENTIST: "deepseek-reasoner",
    AgentRole.LIBRARIAN: "deepseek-chat",
    AgentRole.WRITER: "deepseek-chat",
    AgentRole.CRITIC: "deepseek-reasoner",
    AgentRole.SYNTHESIZER: "deepseek-reasoner",
}

DEEPSEEK_MODELS = {"deepseek-chat", "deepseek-reasoner"}
ANTHROPIC_MODELS = {"claude-opus-4-6", "claude-sonnet-4-6"}

FALLBACK_CHAIN: list[str] = ["deepseek-chat", "step-3.5-flash", "deepseek-reasoner"]


class LLMRouter:
    def __init__(
        self,
        deepseek: DeepSeekProvider | None = None,
        openrouter: OpenRouterProvider | None = None,
        anthropic: AnthropicProvider | None = None,
        tracker: TokenTracker | None = None,
        agent_model_overrides: dict[str, str] | None = None,
    ) -> None:
        self._deepseek = deepseek or DeepSeekProvider()
        self._openrouter = openrouter or OpenRouterProvider()
        self._anthropic = anthropic or AnthropicProvider()
        self._tracker = tracker
        self._local_overrides = agent_model_overrides

    async def close(self) -> None:
        await self._deepseek.close()
        await self._openrouter.close()
        await self._anthropic.close()

    def _is_deepseek(self, model: str) -> bool:
        """Only direct DeepSeek API models. V3.2 Speciale is OpenRouter-only."""
        return model in DEEPSEEK_MODELS

    def _is_anthropic(self, model: str) -> bool:
        return model in ANTHROPIC_MODELS or model.startswith("claude-")

    def _build_fallback_chain(self, model: str) -> list[str]:
        """Build a fallback chain starting with the requested model."""
        chain = [model]
        # Add anthropic models to fallback if key is configured
        if settings.anthropic_api_key:
            for m in ANTHROPIC_MODELS:
                if m != model:
                    chain.append(m)
        for m in FALLBACK_CHAIN:
            if m != model:
                chain.append(m)
        return chain

    def resolve_model(self, role: AgentRole | str | None = None) -> str:
        """Return the model string for a given agent role.

        Priority: local (per-project) overrides -> global user
        overrides -> role defaults -> global default.
        """
        if role is not None:
            key = role.value if isinstance(role, AgentRole) else role
            # 1. Per-project / per-lane local overrides (set via config_json)
            if (self._local_overrides and key in self._local_overrides
                    and self._local_overrides[key]):
                return self._local_overrides[key]
            # 2. Global user overrides (from settings page)
            overrides = settings.agent_model_overrides
            if overrides and key in overrides and overrides[key]:
                return overrides[key]
            # 3. Role defaults
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
        json_mode: bool = False,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await self.call(
            messages=messages,
            model=model,
            project_id=project_id,
            agent_role=agent_role,
            **kwargs,
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

        models_to_try = self._build_fallback_chain(model)
        log.info("LLMRouter.call: model=%s, role=%s, fallback=%s", model, agent_role, models_to_try)

        for m in models_to_try:
            try:
                if self._is_anthropic(m):
                    response = await self._anthropic.call(messages, model=m, **kwargs)
                elif self._is_deepseek(m):
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

        raise RuntimeError(f"All LLM providers failed. Errors: {'; '.join(errors)}")

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
