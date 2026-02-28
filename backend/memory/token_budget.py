"""Token budget manager -- allocates and trims context sections."""

from __future__ import annotations

from dataclasses import dataclass

import tiktoken


@dataclass
class _Section:
    name: str
    content: str
    max_ratio: float | None = None
    fixed: bool = False


class TokenBudget:

    def __init__(self, total: int) -> None:
        self._total = total
        self._encoder = tiktoken.get_encoding("cl100k_base")
        self._sections: list[_Section] = []

    def allocate(
        self,
        section_name: str,
        content: str,
        max_ratio: float | None = None,
        fixed: bool = False,
    ) -> None:
        self._sections.append(_Section(
            name=section_name,
            content=content,
            max_ratio=max_ratio,
            fixed=fixed,
        ))

    def assemble(self) -> str:
        fixed_tokens = sum(
            self._count(s.content) for s in self._sections if s.fixed
        )
        remaining = max(0, self._total - fixed_tokens)

        parts: list[str] = []
        for section in self._sections:
            if not section.content.strip():
                continue
            if section.fixed:
                parts.append(f"## {section.name}\n{section.content}")
            else:
                budget = int(remaining * (section.max_ratio or 0.1))
                trimmed = self._trim(section.content, budget)
                if trimmed.strip():
                    parts.append(f"## {section.name}\n{trimmed}")

        return "\n\n".join(parts)

    def remaining_tokens(self) -> int:
        used = sum(self._count(s.content) for s in self._sections)
        return max(0, self._total - used)

    def _count(self, text: str) -> int:
        return len(self._encoder.encode(text))

    def _trim(self, text: str, max_tokens: int) -> str:
        tokens = self._encoder.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return self._encoder.decode(tokens[:max_tokens])
