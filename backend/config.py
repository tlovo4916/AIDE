"""AIDE configuration -- single source of truth loaded from environment."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "AIDE_", "env_file": ".env", "extra": "ignore"}

    # -- App --
    app_name: str = "AIDE"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # -- Database --
    database_url: str = "postgresql+asyncpg://aide:aide@localhost:5432/aide"
    database_echo: bool = False

    # -- Workspace (file-based blackboard storage) --
    workspace_dir: Path = Path("workspace")

    # -- LLM API keys --
    deepseek_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # -- LLM defaults --
    default_model: str = "deepseek-reasoner"
    orchestrator_model: str = "deepseek-chat"
    embedding_model: str = "text-embedding-3-small"
    summarizer_model: str = "deepseek-chat"

    # -- Per-agent model overrides (role -> model string) --
    agent_model_overrides: dict[str, str] = Field(
        default_factory=lambda: {
            "scientist": "deepseek-chat",
            "librarian": "deepseek-chat",
            "writer": "deepseek-chat",
            "critic": "deepseek-chat",
        }
    )

    # -- ChromaDB --
    chroma_persist_dir: Path = Path("workspace/.chroma")
    chroma_collection: str = "aide_papers"

    # -- PDF processing --
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # -- Retrieval --
    hybrid_search_top_k: int = 20
    mmr_lambda: float = 0.7
    time_decay_factor: float = 0.95
    bm25_weight: float = 0.4
    vector_weight: float = 0.6

    # -- Context budget --
    context_budget_tokens: int = 30000
    core_ratio: float = 0.05
    task_ratio: float = 0.17
    cross_ratio: float = 0.10
    literature_ratio: float = 0.43
    history_ratio: float = 0.07

    # -- Orchestrator --
    max_iterations_per_phase: int = 4
    convergence_min_critic_score: float = 6.0
    convergence_stable_rounds: int = 3
    heartbeat_interval_seconds: int = 60
    heartbeat_stale_threshold_seconds: int = 360

    # -- Checkpoint --
    checkpoint_timeout_minutes: int = 30

    # -- SubAgent --
    max_subagents_per_agent: int = 3

    # -- Web retrieval --
    semantic_scholar_api_key: Optional[str] = None
    enable_web_retrieval: bool = True

    # -- Trend extraction --
    enable_trend_extraction: bool = True
    trend_extraction_interval: int = 2

    @property
    def projects_dir(self) -> Path:
        return self.workspace_dir / "projects"

    def project_path(self, project_id: str) -> Path:
        return self.projects_dir / project_id


settings = Settings()
