"""AIDE configuration -- single source of truth loaded from environment."""

from __future__ import annotations

from pathlib import Path

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
    deepseek_api_key: str | None = None
    openrouter_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    anthropic_base_url: str = "https://api.anthropic.com"

    # -- LLM defaults --
    default_model: str = "deepseek-reasoner"
    orchestrator_model: str = "deepseek-chat"
    embedding_model: str = "qwen/qwen3-embedding-8b"
    summarizer_model: str = "deepseek-chat"

    # -- Per-agent model overrides (role -> model string) --
    agent_model_overrides: dict[str, str] = Field(default_factory=dict)

    # -- Custom presets (name -> {overrides: {role -> model}, description?: str}) --
    custom_presets: dict[str, dict] = Field(default_factory=dict)

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
    heartbeat_stale_threshold_seconds: int = 600
    enable_llm_planner: bool = True
    enable_write_back_guard: bool = True
    convergence_phase_thresholds: dict[str, float] = Field(default_factory=dict)
    topic_drift_embedding_threshold: float = 0.5
    topic_drift_keyword_threshold: float = 0.4

    # -- Checkpoint --
    checkpoint_timeout_minutes: int = 30

    # -- SubAgent --
    max_subagents_per_agent: int = 3

    # -- Web retrieval --
    semantic_scholar_api_key: str | None = None
    enable_web_retrieval: bool = True

    # -- Trend extraction --
    enable_trend_extraction: bool = True
    trend_extraction_interval: int = 2

    # -- Feature flags (Phase 2-4, all off by default) --
    use_semantic_board: bool = False
    use_multi_eval: bool = False
    use_adaptive_planner: bool = False

    # -- Embedding --
    embedding_dimensions: int = 4096

    # -- pgvector --
    pgvector_enabled: bool = True

    # -- Semantic layer (Phase 2 prep) --
    relation_extraction_model: str = "deepseek-chat"
    coverage_recompute_interval: int = 3
    context_semantic_weight: float = 0.50
    context_graph_weight: float = 0.15
    context_recency_weight: float = 0.15
    context_affinity_weight: float = 0.20
    contradiction_confidence_threshold: float = 0.6
    semantic_dedup_threshold: float = 0.85

    # -- Convergence (Phase 3 prep) --
    convergence_info_gain_threshold: float = 0.05
    convergence_gain_window: int = 5
    convergence_loop_threshold: float = 0.8

    # -- Evaluation Engine --
    eval_model: str = "deepseek-chat"
    eval_cross_model: bool = True
    eval_computable_weight: float = 0.6
    eval_llm_weight: float = 0.4
    eval_claim_extraction_model: str = "deepseek-chat"
    eval_contradiction_threshold: float = 0.75
    eval_info_gain_window: int = 5
    eval_info_gain_threshold: float = 0.05
    eval_loop_jaccard_threshold: float = 0.8

    # -- Migration --
    migrate_on_start: bool = False

    @property
    def projects_dir(self) -> Path:
        return self.workspace_dir / "projects"

    def project_path(self, project_id: str) -> Path:
        return self.projects_dir / project_id


settings = Settings()
