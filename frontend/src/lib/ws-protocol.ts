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
}

export interface CheckpointResolvedPayload {
  id: string;
  response: string;
}

export interface PhaseAdvancedPayload {
  from_phase: string;
  phase: string;
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
}

export interface ChallengeResolvedPayload {
  id: string;
  resolution: string;
}

export interface ArtifactUpdatedPayload {
  artifact_type: string;
  artifact_id: string;
  action: "created" | "updated" | "deleted";
  data: Record<string, unknown>;
}

// Union of all push event names
export type WSPushEvent =
  | "CheckpointCreated"
  | "CheckpointResolved"
  | "PhaseAdvanced"
  | "Backtrack"
  | "AgentActivity"
  | "SubAgentSpawned"
  | "SubAgentCompleted"
  | "ChallengeRaised"
  | "ChallengeResolved"
  | "ArtifactUpdated";

export type WSPushPayloadMap = {
  CheckpointCreated: CheckpointCreatedPayload;
  CheckpointResolved: CheckpointResolvedPayload;
  PhaseAdvanced: PhaseAdvancedPayload;
  Backtrack: BacktrackPayload;
  AgentActivity: AgentActivityPayload;
  SubAgentSpawned: SubAgentSpawnedPayload;
  SubAgentCompleted: SubAgentCompletedPayload;
  ChallengeRaised: ChallengeRaisedPayload;
  ChallengeResolved: ChallengeResolvedPayload;
  ArtifactUpdated: ArtifactUpdatedPayload;
};
