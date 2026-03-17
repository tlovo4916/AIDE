export enum WSFrameType {
  REQUEST = "request",
  RESPONSE = "response",
  PUSH = "push",
}

export interface WSFrame<P = unknown> {
  type: WSFrameType;
  event: string;
  payload: P;
  request_id?: string;
}

// --- Push Event Payloads ---

export interface CheckpointCreatedPayload {
  id: string;
  phase: string;
  summary: string;
  options: { label: string; value: string }[];
  lane_index?: number;
}

export interface CheckpointResolvedPayload {
  id: string;
  response: string;
}

export interface PhaseAdvancedPayload {
  from_phase: string;
  phase: string;
  lane_index?: number;
}

export interface BacktrackPayload {
  from_phase: string;
  to_phase: string;
  reason: string;
}

export interface AgentActivityPayload {
  agent: string;
  action: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
  lane_index?: number;
}

export interface SubAgentSpawnedPayload {
  parent_agent: string;
  child_agent: string;
  task: string;
}

export interface SubAgentCompletedPayload {
  agent: string;
  result_summary: string;
}

export interface ChallengeRaisedPayload {
  id: string;
  from: string;
  target: string;
  message: string;
  lane_index?: number;
}

export interface ChallengeResolvedPayload {
  id: string;
  resolution: string;
  lane_index?: number;
}

export interface ArtifactUpdatedPayload {
  artifact_type: string;
  artifact_id: string;
  action: "created" | "updated" | "deleted";
  data: Record<string, unknown>;
  quality_score?: number;
  embedding_status?: "pending" | "completed" | "failed";
  relations?: { target_id: string; relation_type: string }[];
  lane_index?: number;
}

export interface AgentStartedPayload {
  agent: string;
  task: string;
  phase: string;
  iteration: number;
  timestamp: string;
  lane_index?: number;
}

export interface AgentErrorPayload {
  agent: string;
  error: string;
  iteration: number;
}

export interface TopicDriftWarningPayload {
  iteration: number;
  research_topic: string;
  match_ratio: number;
  message: string;
}

export interface TokenUsageSummary {
  project_id: string;
  by_model: Record<string, {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    cost_usd: number;
    calls: number;
  }>;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  total_cost_rmb: number;
  total_calls: number;
}

export interface ResearchCompletedPayload {
  phase: string;
  paper_path: string | null;
  token_usage: TokenUsageSummary | null;
}

export interface LanesStartedPayload {
  num_lanes: number;
  project_id: string;
}

export interface LaneCompletedPayload {
  lane: number;
  error?: boolean;
}

export interface SynthesisStartedPayload {
  num_lanes: number;
}

export interface EvaluationCompletedPayload {
  iteration: number;
  phase: string;
  composite_score: number;
  dimensions: Record<string, number>;
  evaluator_model: string;
  information_gain?: number;
}

export interface PlannerDecisionPayload {
  iteration: number;
  phase: string;
  chosen_agent: string;
  rationale: string;
  candidates: { agent: string; score: number }[];
}

// Union of all push event names
export type WSPushEvent =
  | "CheckpointCreated"
  | "CheckpointResolved"
  | "PhaseAdvanced"
  | "Backtrack"
  | "AgentStarted"
  | "AgentActivity"
  | "AgentError"
  | "SubAgentSpawned"
  | "SubAgentCompleted"
  | "ChallengeRaised"
  | "ChallengeResolved"
  | "ArtifactUpdated"
  | "TopicDriftWarning"
  | "ResearchCompleted"
  | "LanesStarted"
  | "LaneCompleted"
  | "SynthesisStarted"
  | "EvaluationCompleted"
  | "PlannerDecision";

export type WSPushPayloadMap = {
  CheckpointCreated: CheckpointCreatedPayload;
  CheckpointResolved: CheckpointResolvedPayload;
  PhaseAdvanced: PhaseAdvancedPayload;
  Backtrack: BacktrackPayload;
  AgentStarted: AgentStartedPayload;
  AgentActivity: AgentActivityPayload;
  AgentError: AgentErrorPayload;
  SubAgentSpawned: SubAgentSpawnedPayload;
  SubAgentCompleted: SubAgentCompletedPayload;
  ChallengeRaised: ChallengeRaisedPayload;
  ChallengeResolved: ChallengeResolvedPayload;
  ArtifactUpdated: ArtifactUpdatedPayload;
  TopicDriftWarning: TopicDriftWarningPayload;
  ResearchCompleted: ResearchCompletedPayload;
  LanesStarted: LanesStartedPayload;
  LaneCompleted: LaneCompletedPayload;
  SynthesisStarted: SynthesisStartedPayload;
  EvaluationCompleted: EvaluationCompletedPayload;
  PlannerDecision: PlannerDecisionPayload;
};
