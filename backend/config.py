"""AIDE configuration -- single source of truth loaded from environment."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "AIDE_", "env_file": ".env", "extra": "ignore"}

    # =====================================================================
    # 1. Core — server identity and storage paths.
    #    Rarely need changing outside of deployment.
    # =====================================================================
    app_name: str = "AIDE"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = "postgresql+asyncpg://aide:aide@localhost:5432/aide"
    database_echo: bool = False
    workspace_dir: Path = Path("workspace")

    # =====================================================================
    # 2. LLM Providers & Model Selection
    #    Set API keys for the providers you use. default_model is the
    #    fallback; per-role overrides go in agent_model_overrides.
    #    Changing models affects cost, latency, and output quality.
    # =====================================================================
    deepseek_api_key: str | None = None
    openrouter_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    anthropic_base_url: str = "https://api.anthropic.com"
    default_model: str = Field(
        "deepseek-reasoner",
        description="Fallback model when no role-specific override is set",
    )
    orchestrator_model: str = Field(
        "deepseek-chat",
        description="Model used by the planner for LLM-based scheduling decisions",
    )
    embedding_model: str = Field(
        "qwen/qwen3-embedding-8b",
        description="Model for generating text embeddings (via OpenRouter)",
    )
    summarizer_model: str = Field(
        "deepseek-chat",
        description="Model for context summarization when budget is exceeded",
    )
    agent_model_overrides: dict[str, str] = Field(
        default_factory=dict,
        description="Per-role model overrides, e.g. {'scientist': 'claude-sonnet-4-6'}",
    )
    custom_presets: dict[str, dict] = Field(
        default_factory=dict,
        description="User-defined model preset bundles (name -> role->model map)",
    )

    # =====================================================================
    # 3. Vector Store (ChromaDB & pgvector)
    #    ChromaDB is used for BM25+vector hybrid search on retrieved papers.
    #    pgvector stores artifact embeddings in PostgreSQL for semantic board.
    #    embedding_dimensions MUST match the output of embedding_model.
    # =====================================================================
    chroma_persist_dir: Path = Path("workspace/.chroma")
    chroma_collection: str = "aide_papers"
    chunk_size: int = Field(1000, description="Characters per chunk when splitting documents")
    chunk_overlap: int = Field(200, description="Overlap between adjacent chunks")
    pgvector_enabled: bool = Field(True, description="Use pgvector for DB-level vector search")
    embedding_dimensions: int = Field(
        4096, description="Vector dimensionality — must match embedding_model output"
    )

    # =====================================================================
    # 4. Hybrid Search (BM25 + Vector)
    #    Tuning: raise bm25_weight for keyword-heavy queries; raise
    #    vector_weight for semantic similarity. mmr_lambda trades off
    #    relevance vs diversity in re-ranked results.
    # =====================================================================
    hybrid_search_top_k: int = Field(20, description="Candidates retrieved before re-ranking")
    mmr_lambda: float = Field(
        0.7, description="MMR diversity param: 1.0 = pure relevance, 0.0 = pure diversity"
    )
    time_decay_factor: float = Field(
        0.95, description="Per-day decay multiplier for older documents (0.95^days)"
    )
    bm25_weight: float = Field(0.4, description="BM25 score weight in hybrid fusion")
    vector_weight: float = Field(0.6, description="Vector similarity weight in hybrid fusion")

    # =====================================================================
    # 5. Context Budget (token allocation ratios for agent context)
    #    Ratios should sum to ~1.0. Increasing literature_ratio helps
    #    evidence-heavy phases; increasing history_ratio helps continuity.
    # =====================================================================
    context_budget_tokens: int = Field(30000, description="Max tokens in agent context window")
    core_ratio: float = Field(0.05, description="Budget share for core state summary")
    task_ratio: float = Field(0.17, description="Budget share for current task description")
    cross_ratio: float = Field(0.10, description="Budget share for cross-agent artifacts")
    literature_ratio: float = Field(0.43, description="Budget share for retrieved literature")
    history_ratio: float = Field(0.07, description="Budget share for conversation history")

    # =====================================================================
    # 6. Orchestration & Phase Control
    #    Controls iteration limits, phase transitions, and crash detection.
    #    Lower max_iterations_per_phase for faster but shallower research.
    #    Higher convergence_stable_rounds requires more consistent quality.
    # =====================================================================
    max_iterations_per_phase: int = Field(
        4, description="Hard cap — forces phase advance after N iterations"
    )
    convergence_min_critic_score: float = Field(
        6.0, description="Critic score >= this to satisfy quality convergence condition"
    )
    convergence_stable_rounds: int = Field(
        3, description="Consecutive rounds above threshold needed to converge"
    )
    heartbeat_interval_seconds: int = 60
    heartbeat_stale_threshold_seconds: int = Field(
        600, description="Seconds without heartbeat before engine is considered crashed"
    )
    checkpoint_timeout_minutes: int = Field(
        30, description="User approval timeout — auto-selects default after this"
    )
    max_subagents_per_agent: int = 3
    enable_llm_planner: bool = Field(
        True, description="Use LLM for scheduling decisions (False = rule-based rotation)"
    )
    enable_write_back_guard: bool = Field(
        True, description="Validate agent actions before writing to board"
    )
    convergence_phase_thresholds: dict[str, float] = Field(
        default_factory=dict,
        description="Per-phase critic score overrides, e.g. {'explore': 5.0, 'compose': 7.0}",
    )
    topic_drift_embedding_threshold: float = Field(
        0.5, description="Cosine similarity below this triggers topic drift warning"
    )
    topic_drift_keyword_threshold: float = Field(
        0.4, description="Keyword overlap below this triggers topic drift warning"
    )

    # =====================================================================
    # 7. Web Retrieval (arXiv / Semantic Scholar)
    #    Papers are fetched from S2 and arXiv. Set semantic_scholar_api_key
    #    for higher rate limits. trend_extraction_interval controls how
    #    often emerging-topic signals are computed from evidence artifacts.
    # =====================================================================
    semantic_scholar_api_key: str | None = None
    enable_web_retrieval: bool = True
    enable_trend_extraction: bool = True
    trend_extraction_interval: int = Field(
        2, description="Run trend extraction every N iterations"
    )

    # =====================================================================
    # 8. Feature Flags
    #    Master switches for major subsystems. Disabling any of these
    #    reverts to the simpler Phase 1 behaviour for that subsystem.
    # =====================================================================
    use_semantic_board: bool = Field(
        True, description="Enable Phase 2 semantic board (DB dual-write, relations, coverage)"
    )
    use_multi_eval: bool = Field(
        True, description="Enable Phase 3 multi-dimensional evaluation engine"
    )
    use_adaptive_planner: bool = Field(
        True, description="Enable Phase 4 adaptive planner (state-aware agent dispatch)"
    )

    # =====================================================================
    # 9. Semantic Layer (Phase 2)
    #    Controls DB-backed artifact relations, coverage analysis, and
    #    semantic context ranking. Weights in context_*_weight determine
    #    how artifacts are prioritised when building agent context.
    # =====================================================================
    relation_extraction_model: str = Field(
        "deepseek-chat", description="Model for extracting inter-artifact relations"
    )
    coverage_recompute_interval: int = Field(
        3, description="Recompute topic coverage gaps every N iterations"
    )
    context_semantic_weight: float = Field(
        0.50, description="Weight for embedding similarity in context ranking"
    )
    context_graph_weight: float = Field(
        0.15, description="Weight for graph-distance in context ranking"
    )
    context_recency_weight: float = Field(
        0.15, description="Weight for time-decay in context ranking"
    )
    context_affinity_weight: float = Field(
        0.20, description="Weight for role-artifact affinity in context ranking"
    )
    contradiction_confidence_threshold: float = Field(
        0.6, description="Min confidence to flag a contradiction between claims"
    )
    semantic_dedup_threshold: float = Field(
        0.85, description="Cosine similarity above this deduplicates artifacts"
    )

    # =====================================================================
    # 10. Evaluation Engine (Phase 3)
    #    Multi-dimensional scoring with computable+LLM hybrid metrics.
    #    eval_cross_model uses a different model for evaluation than the
    #    generator to reduce self-bias. eval_interval controls frequency.
    # =====================================================================
    eval_model: str = Field(
        "deepseek-chat", description="Model for LLM-based evaluation scoring"
    )
    eval_cross_model: bool = Field(
        True, description="Use a different model than the agent for evaluation"
    )
    eval_computable_weight: float = Field(
        0.6, description="Weight for computable metrics (Jaccard, ROUGE, etc.)"
    )
    eval_llm_weight: float = Field(
        0.4, description="Weight for LLM-judged quality dimensions"
    )
    eval_claim_extraction_model: str = Field(
        "deepseek-chat", description="Model for extracting claims from research output"
    )
    eval_contradiction_threshold: float = Field(
        0.75, description="Similarity above this between opposing claims flags contradiction"
    )
    eval_info_gain_window: int = Field(
        5, description="Number of recent iterations to compute information gain over"
    )
    eval_info_gain_threshold: float = Field(
        0.05, description="Info gain below this suggests research is stagnating"
    )
    eval_loop_jaccard_threshold: float = Field(
        0.8, description="Jaccard overlap above this between iterations detects loops"
    )
    eval_interval: int = Field(
        3, description="Run full evaluation every N iterations"
    )

    # =====================================================================
    # 11. Convergence (Phase 3)
    #    Thresholds that determine when a research phase has exhausted
    #    its information potential and should advance.
    # =====================================================================
    convergence_info_gain_threshold: float = Field(
        0.05, description="Info gain below this satisfies information-exhaustion condition"
    )
    convergence_gain_window: int = Field(
        5, description="Number of recent iterations to average info gain over"
    )
    convergence_loop_threshold: float = Field(
        0.8, description="Jaccard overlap above this counts as a loop iteration"
    )

    # =====================================================================
    # 12. Adaptive Planner (Phase 4) [experimental]
    #    State-aware agent dispatch scoring. Bonuses/penalties steer the
    #    scheduler toward agents whose work is most needed. tie_threshold
    #    determines when LLM arbitration kicks in (~10% of iterations).
    # =====================================================================
    adaptive_phase_bonus: float = Field(
        0.2, description="Score bonus for the agent whose primary artifact matches current phase"
    )
    adaptive_non_phase_penalty: float = Field(
        0.3, description="Score penalty for agents not aligned with current phase"
    )
    adaptive_request_bonus_cap: float = Field(
        0.5, description="Max bonus from pending InfoRequests targeting an agent"
    )
    adaptive_repetition_penalty: float = Field(
        0.15, description="Per-consecutive-dispatch penalty to avoid repeating same agent"
    )
    adaptive_tie_threshold: float = Field(
        0.1, description="Score gap below this triggers LLM tie-breaker instead of top pick"
    )

    # =====================================================================
    # 13. Migration
    # =====================================================================
    migrate_on_start: bool = False

    @property
    def projects_dir(self) -> Path:
        return self.workspace_dir / "projects"

    def project_path(self, project_id: str) -> Path:
        return self.projects_dir / project_id


settings = Settings()
