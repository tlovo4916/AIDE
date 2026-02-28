"""AIDE shared types -- enums, data models, and protocol definitions."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AgentRole(str, Enum):
    DIRECTOR = "director"
    SCIENTIST = "scientist"
    LIBRARIAN = "librarian"
    WRITER = "writer"
    CRITIC = "critic"


class ResearchPhase(str, Enum):
    EXPLORE = "explore"
    HYPOTHESIZE = "hypothesize"
    EVIDENCE = "evidence"
    COMPOSE = "compose"
    COMPLETE = "complete"


class ArtifactType(str, Enum):
    DIRECTIONS = "directions"
    HYPOTHESES = "hypotheses"
    EVIDENCE_FINDINGS = "evidence_findings"
    EVIDENCE_GAPS = "evidence_gaps"
    EXPERIMENT_GUIDE = "experiment_guide"
    OUTLINE = "outline"
    DRAFT = "draft"
    REVIEW = "review"


class ContextLevel(str, Enum):
    L0 = "l0"
    L1 = "l1"
    L2 = "l2"


class ActionType(str, Enum):
    WRITE_ARTIFACT = "write_artifact"
    POST_MESSAGE = "post_message"
    RAISE_CHALLENGE = "raise_challenge"
    RESOLVE_CHALLENGE = "resolve_challenge"
    REQUEST_INFO = "request_info"
    SPAWN_SUBAGENT = "spawn_subagent"


class ChallengeStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class CheckpointAction(str, Enum):
    APPROVE = "approve"
    ADJUST = "adjust"
    SKIP = "skip"


class TaskPriority(str, Enum):
    CRITICAL = "critical"
    NORMAL = "normal"
    EXPLORATORY = "exploratory"


class DedupDecision(str, Enum):
    SKIP = "skip"
    CREATE = "create"
    MERGE = "merge"
    SUPERSEDE = "supersede"


class WSFrameType(str, Enum):
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
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
    response: Optional[str] = None
    responder: Optional[AgentRole] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


class Message(BaseModel):
    message_id: str
    from_agent: AgentRole
    to_agent: Optional[AgentRole] = None  # None = broadcast
    content: str
    refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DecisionRecord(BaseModel):
    decision_id: str
    phase: ResearchPhase
    context_summary: str
    options: list[str]
    chosen: str
    rationale: str
    decided_by: AgentRole
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Orchestrator models
# ---------------------------------------------------------------------------

class OrchestratorDecision(BaseModel):
    agent_to_invoke: AgentRole
    task_description: str
    task_priority: TaskPriority = TaskPriority.NORMAL
    allow_subagents: bool = False
    trigger_checkpoint: bool = False
    checkpoint_reason: Optional[str] = None
    backtrack_to: Optional[ResearchPhase] = None
    rationale: str = ""


class ConvergenceSignals(BaseModel):
    open_challenges: int = 0
    critic_score: float = 0.0
    recent_revision_count: int = 0
    iteration_count: int = 0
    is_converged: bool = False


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
    model_override: Optional[str] = None


class SubAgentResult(BaseModel):
    subagent_id: str
    parent_role: AgentRole
    task: str
    output: dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Checkpoint models
# ---------------------------------------------------------------------------

class CheckpointEvent(BaseModel):
    checkpoint_id: str
    project_id: str
    phase: ResearchPhase
    reason: str
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user_action: Optional[CheckpointAction] = None
    user_feedback: Optional[str] = None
    resolved_at: Optional[datetime] = None
    timeout_minutes: int = 30


# ---------------------------------------------------------------------------
# WebSocket protocol
# ---------------------------------------------------------------------------

class WSFrame(BaseModel):
    type: WSFrameType
    event: str
    payload: dict[str, Any] = Field(default_factory=dict)
    request_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Search models
# ---------------------------------------------------------------------------

class SearchResult(BaseModel):
    chunk_id: str
    content: str
    source: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    publish_date: Optional[datetime] = None
