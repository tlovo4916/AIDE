"""AIDE shared types -- enums, data models, and protocol definitions."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AgentRole(StrEnum):
    DIRECTOR = "director"
    SCIENTIST = "scientist"
    LIBRARIAN = "librarian"
    WRITER = "writer"
    CRITIC = "critic"
    SYNTHESIZER = "synthesizer"


class ResearchPhase(StrEnum):
    EXPLORE = "explore"
    HYPOTHESIZE = "hypothesize"
    EVIDENCE = "evidence"
    COMPOSE = "compose"
    SYNTHESIZE = "synthesize"
    COMPLETE = "complete"


class ArtifactType(StrEnum):
    DIRECTIONS = "directions"
    HYPOTHESES = "hypotheses"
    EVIDENCE_FINDINGS = "evidence_findings"
    EVIDENCE_GAPS = "evidence_gaps"
    EXPERIMENT_GUIDE = "experiment_guide"
    OUTLINE = "outline"
    DRAFT = "draft"
    REVIEW = "review"
    TREND_SIGNALS = "trend_signals"


class ContextLevel(StrEnum):
    L0 = "l0"
    L1 = "l1"
    L2 = "l2"


class ActionType(StrEnum):
    WRITE_ARTIFACT = "write_artifact"
    POST_MESSAGE = "post_message"
    RAISE_CHALLENGE = "raise_challenge"
    RESOLVE_CHALLENGE = "resolve_challenge"
    REQUEST_INFO = "request_info"
    SPAWN_SUBAGENT = "spawn_subagent"


class ChallengeStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class CheckpointAction(StrEnum):
    APPROVE = "approve"
    ADJUST = "adjust"
    SKIP = "skip"


class TaskPriority(StrEnum):
    CRITICAL = "critical"
    NORMAL = "normal"
    EXPLORATORY = "exploratory"


class DedupDecision(StrEnum):
    SKIP = "skip"
    CREATE = "create"
    MERGE = "merge"
    SUPERSEDE = "supersede"


class WSFrameType(StrEnum):
    REQUEST = "request"
    RESPONSE = "response"
    PUSH = "push"


# ---------------------------------------------------------------------------
# Blackboard data models
# ---------------------------------------------------------------------------


class ArtifactMeta(BaseModel):
    artifact_type: ArtifactType
    artifact_id: str
    version: int = 1
    created_by: AgentRole
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    active_count: int = 0
    superseded: bool = False
    tags: list[str] = Field(default_factory=list)


class BlackboardAction(BaseModel):
    agent_role: AgentRole
    action_type: ActionType
    target: str
    content: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""
    context_level: ContextLevel = ContextLevel.L1


class ChallengeRecord(BaseModel):
    challenge_id: str
    status: ChallengeStatus = ChallengeStatus.OPEN
    challenger: AgentRole
    target_artifact: str
    argument: str
    evidence_refs: list[str] = Field(default_factory=list)
    response: str | None = None
    responder: AgentRole | None = None
    target_agent: AgentRole | None = None  # Agent that should respond to this challenge
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None


class Message(BaseModel):
    message_id: str
    from_agent: AgentRole
    to_agent: AgentRole | None = None  # None = broadcast
    content: str
    refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DecisionRecord(BaseModel):
    decision_id: str
    phase: ResearchPhase
    context_summary: str
    options: list[str]
    chosen: str
    rationale: str
    decided_by: AgentRole
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Orchestrator models
# ---------------------------------------------------------------------------


class OrchestratorDecision(BaseModel):
    agent_to_invoke: AgentRole
    task_description: str
    task_priority: TaskPriority = TaskPriority.NORMAL
    allow_subagents: bool = False
    trigger_checkpoint: bool = False
    checkpoint_reason: str | None = None
    backtrack_to: ResearchPhase | None = None
    rationale: str = ""
    candidate_scores: list[dict] | None = None


class ConvergenceSignals(BaseModel):
    open_challenges: int = 0
    critic_score: float = 0.0
    recent_revision_count: int = 0
    iteration_count: int = 0
    is_converged: bool = False
    eval_composite: float | None = None
    information_gain: float | None = None
    is_diminishing: bool = False


# ---------------------------------------------------------------------------
# Agent models
# ---------------------------------------------------------------------------


class AgentTask(BaseModel):
    task_id: str
    description: str
    priority: TaskPriority = TaskPriority.NORMAL
    target_artifacts: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    allow_subagents: bool = False


class AgentResponse(BaseModel):
    actions: list[BlackboardAction] = Field(default_factory=list)
    reasoning_summary: str = ""
    subagent_requests: list[SubAgentRequest] = Field(default_factory=list)


class SubAgentRequest(BaseModel):
    task: str
    tools: list[str] = Field(default_factory=list)
    model_override: str | None = None


class SubAgentResult(BaseModel):
    subagent_id: str
    parent_role: AgentRole
    task: str
    output: dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error: str | None = None


# ---------------------------------------------------------------------------
# Checkpoint models
# ---------------------------------------------------------------------------


class CheckpointEvent(BaseModel):
    checkpoint_id: str
    project_id: str
    phase: ResearchPhase
    reason: str
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    user_action: CheckpointAction | None = None
    user_feedback: str | None = None
    resolved_at: datetime | None = None
    timeout_minutes: int = 30


# ---------------------------------------------------------------------------
# WebSocket protocol
# ---------------------------------------------------------------------------


class WSFrame(BaseModel):
    type: WSFrameType
    event: str
    payload: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


# ---------------------------------------------------------------------------
# Search models
# ---------------------------------------------------------------------------


class SearchResult(BaseModel):
    chunk_id: str
    content: str
    source: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    publish_date: datetime | None = None


# ---------------------------------------------------------------------------
# Evaluation Engine models
# ---------------------------------------------------------------------------


class EvaluationDimension(StrEnum):
    COVERAGE_BREADTH = "coverage_breadth"
    SOURCE_DIVERSITY = "source_diversity"
    TERMINOLOGY_COVERAGE = "terminology_coverage"
    SPECIFICITY = "specificity"
    NOVELTY = "novelty"
    LOGICAL_COHERENCE = "logical_coherence"
    CITATION_DENSITY = "citation_density"
    EVIDENCE_MAPPING = "evidence_mapping"
    METHODOLOGICAL_RIGOR = "methodological_rigor"
    STRUCTURAL_COMPLETENESS = "structural_completeness"
    ARGUMENT_FLOW = "argument_flow"
    CITATION_INTEGRATION = "citation_integration"
    INTERNAL_CONSISTENCY = "internal_consistency"


class DimensionScore(BaseModel):
    name: str
    computable_value: float | None = None
    llm_value: float | None = None
    combined: float = 0.0
    weight: float = 1.0
    evidence: list[str] = Field(default_factory=list)


class PhaseEvaluation(BaseModel):
    phase: ResearchPhase
    dimensions: dict[str, DimensionScore] = Field(default_factory=dict)
    composite_score: float = 0.0
    evaluator_model: str = ""
    evaluator_provider: str = ""
    raw_evidence: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Claim(BaseModel):
    claim_id: str
    text: str
    source_artifact: str
    claim_type: str = ""
    confidence: str = "moderate"
    embedding: list[float] = Field(default_factory=list)


class Contradiction(BaseModel):
    contradiction_id: str
    claim_a: Claim
    claim_b: Claim
    relationship: str = "contradictory"
    explanation: str = ""
    severity: float = 0.5
    detected_by: str = ""


class InformationGainMetric(BaseModel):
    iteration: int
    information_gain: float = 0.0
    artifact_count_delta: int = 0
    unique_claim_delta: int = 0
    is_diminishing: bool = False
    is_loop_detected: bool = False


class BenchmarkTask(BaseModel):
    task_id: str
    research_topic: str
    phase: str
    input_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    expected_evaluation: dict[str, Any] = Field(default_factory=dict)
    expected_contradictions: list[dict[str, Any]] = Field(default_factory=list)
    expected_convergence: bool | None = None
    description: str = ""


class BenchmarkResult(BaseModel):
    task_id: str
    config_name: str = "baseline"
    evaluation: PhaseEvaluation | None = None
    contradictions_found: list[Contradiction] = Field(default_factory=list)
    convergence_metric: InformationGainMetric | None = None
    passed: bool = False
    duration_seconds: float = 0.0
    error: str | None = None
