"""Agent module -- specialist research agents and factory."""

from backend.agents.base import BaseAgent, WriteBackGuard
from backend.agents.critic import CriticAgent
from backend.agents.director import DirectorAgent
from backend.agents.librarian import LibrarianAgent
from backend.agents.scientist import ScientistAgent
from backend.agents.subagent import SubAgent, SubAgentPool
from backend.agents.writer import WriterAgent
from backend.protocols import LLMRouter
from backend.types import AgentRole


def get_agent(
    role: AgentRole,
    llm_router: LLMRouter,
    write_back_guard: WriteBackGuard,
) -> BaseAgent:
    """Factory: instantiate the specialist agent for *role*."""
    registry: dict[AgentRole, type[BaseAgent]] = {
        AgentRole.DIRECTOR: DirectorAgent,
        AgentRole.SCIENTIST: ScientistAgent,
        AgentRole.LIBRARIAN: LibrarianAgent,
        AgentRole.WRITER: WriterAgent,
        AgentRole.CRITIC: CriticAgent,
    }
    cls = registry.get(role)
    if cls is None:
        raise ValueError(f"Unknown agent role: {role!r}")
    return cls(llm_router, write_back_guard)


__all__ = [
    "BaseAgent",
    "CriticAgent",
    "DirectorAgent",
    "LLMRouter",
    "LibrarianAgent",
    "ScientistAgent",
    "SubAgent",
    "SubAgentPool",
    "WriteBackGuard",
    "WriterAgent",
    "get_agent",
]
