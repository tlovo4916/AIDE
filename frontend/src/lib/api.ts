/**
 * AIDE API Client
 *
 * Sections:
 *   1. Core (request helper)
 *   2. Projects (CRUD + lifecycle)
 *   3. Papers (upload, search, export)
 *   4. Checkpoints (list, respond)
 *   5. Settings (read, update)
 *   6. Blackboard (artifacts, challenges, messages)
 *   7. Lanes (multi-lane statuses)
 *   8. Citation Graph
 *   9. Token Usage
 *  10. Evaluations (scores, metrics, claims, contradictions)
 */

// =====================================================================
// 1. Core
// =====================================================================

function getApiBase(): string {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:30001`;
  }
  return "http://localhost:30001";
}

const API_BASE = getApiBase();

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// =====================================================================
// 2. Projects
// =====================================================================

export interface CreateProjectPayload {
  name: string;
  research_topic: string;
  concurrency?: number;
  paper_ids?: string[];
  config_json?: {
    lane_overrides?: Record<string, string>[];
    embedding_model?: string;
  };
}

export function createProject(payload: CreateProjectPayload) {
  return request<{ id: string }>("/api/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listProjects() {
  return request<
    {
      id: string;
      name: string;
      research_topic: string;
      concurrency?: number;
      phase: string;
      status: string;
      created_at: string;
    }[]
  >("/api/projects");
}

export function getProject(id: string) {
  return request<{
    id: string;
    name: string;
    research_topic: string;
    concurrency?: number;
    phase: string;
    status: string;
    created_at: string;
    updated_at: string;
  }>(`/api/projects/${id}`);
}

export function deleteProject(id: string) {
  return request<void>(`/api/projects/${id}`, { method: "DELETE" });
}

export function startProject(id: string) {
  return request<{ id: string; status: string }>(`/api/projects/${id}/start`, {
    method: "POST",
  });
}

export function pauseProject(id: string) {
  return request<{ id: string; status: string }>(`/api/projects/${id}/pause`, {
    method: "POST",
  });
}

export function resumeProject(id: string) {
  return request<{ id: string; status: string }>(
    `/api/projects/${id}/resume`,
    { method: "POST" }
  );
}

// =====================================================================
// 3. Papers
// =====================================================================

export function uploadPaper(projectId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<{ paper_id: string; filename: string; size_bytes: number }>(
    `/api/projects/${projectId}/papers/upload`,
    {
      method: "POST",
      headers: {},
      body: form,
    }
  );
}

export function listPapers(projectId: string) {
  return request<
    { paper_id: string; filename: string; size_bytes: number }[]
  >(`/api/projects/${projectId}/papers`);
}

export function deletePaper(projectId: string, paperId: string) {
  return request<void>(`/api/projects/${projectId}/papers/${paperId}`, {
    method: "DELETE",
  });
}

export function searchPapers(projectId: string, query: string) {
  return request<
    {
      chunk_id: string;
      content: string;
      source: string;
      score: number;
      metadata: Record<string, unknown>;
    }[]
  >(
    `/api/projects/${projectId}/papers/search?q=${encodeURIComponent(query)}`
  );
}

export function getExportedPaper(projectId: string) {
  return request<{ content: string; filename: string }>(
    `/api/projects/${projectId}/export/paper`
  );
}

export function getPaperHtml(projectId: string) {
  return request<{ html: string; title: string }>(
    `/api/projects/${projectId}/export/paper/html`
  );
}

export function savePaperContent(projectId: string, content: string) {
  return request<void>(`/api/projects/${projectId}/export/paper`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
}

// =====================================================================
// 4. Checkpoints
// =====================================================================

export function listCheckpoints(projectId: string) {
  return request<
    {
      id: string;
      phase: string;
      summary: string;
      status: string;
      created_at: string;
    }[]
  >(`/api/projects/${projectId}/checkpoints`);
}

export function respondToCheckpoint(
  projectId: string,
  checkpointId: string,
  action: string
) {
  return request<void>(
    `/api/projects/${projectId}/checkpoints/${checkpointId}/respond`,
    {
      method: "POST",
      body: JSON.stringify({ action }),
    }
  );
}

// =====================================================================
// 5. Settings
// =====================================================================

export function getSettings() {
  return request<Record<string, unknown>>("/api/settings");
}

export function updateSettings(settings: Record<string, unknown>) {
  return request<void>("/api/settings", {
    method: "PUT",
    body: JSON.stringify(settings),
  });
}

// =====================================================================
// 6. Blackboard
// =====================================================================

export function getBlackboard(projectId: string, lane?: number) {
  const params = lane !== undefined ? `?lane=${lane}` : "";
  return request<{
    artifacts: Record<string, { id: string; type: string; data: Record<string, unknown> }[]>;
    challenges: { id: string; from: string; message: string; resolved: boolean }[];
    messages: { id: string; role: string; content: string; timestamp: string }[];
  }>(`/api/projects/${projectId}/blackboard${params}`);
}

// =====================================================================
// 7. Lanes
// =====================================================================

export interface LaneStatus {
  lane: number;
  phase: string;
  iteration: number;
}

export function getLaneStatuses(projectId: string) {
  return request<LaneStatus[]>(`/api/projects/${projectId}/lanes`);
}

// =====================================================================
// 8. Citation Graph
// =====================================================================

export interface CitationGraphData {
  nodes: {
    id: string;
    title?: string;
    year?: number;
    authors?: string;
    source?: string;
    url?: string;
    citation_count: number;
  }[];
  edges: { source: string; target: string }[];
  most_cited: string[];
  total_papers: number;
}

export function getCitationGraph(projectId: string) {
  return request<CitationGraphData>(`/api/projects/${projectId}/citation-graph`);
}

// =====================================================================
// 9. Token Usage
// =====================================================================

export interface ProjectTokenUsage {
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

export function getProjectUsage(projectId: string) {
  return request<ProjectTokenUsage>(`/api/projects/${projectId}/usage`);
}

// =====================================================================
// 10. Evaluations
// =====================================================================

export interface EvaluationResult {
  id: string;
  phase: string;
  iteration: number;
  composite_score: number;
  evaluator_model: string;
  dimensions: Record<string, {
    computable_value?: number;
    llm_value?: number;
    combined: number;
    weight: number;
    evidence?: string;
  }>;
  created_at: string;
}

export interface IterationMetric {
  id: string;
  phase: string;
  iteration: number;
  information_gain: number | null;
  eval_composite: number | null;
  artifact_count_delta: number | null;
  unique_claim_delta: number | null;
  metrics: Record<string, unknown> | null;
  created_at: string;
}

export interface ClaimData {
  claim_id: string;
  text: string;
  source_artifact: string;
  confidence: "strong" | "moderate" | "tentative";
}

export interface ContradictionData {
  id: string;
  claim_a_id: string;
  claim_b_id: string;
  confidence: number;
  evidence: Record<string, unknown>;
  status: string;
}

export function getEvaluations(projectId: string, limit = 100) {
  return request<EvaluationResult[]>(
    `/api/projects/${projectId}/evaluations?limit=${limit}`
  );
}

export function getIterationMetrics(projectId: string, limit = 100) {
  return request<IterationMetric[]>(
    `/api/projects/${projectId}/iteration-metrics?limit=${limit}`
  );
}

export function getClaims(projectId: string, limit = 100) {
  return request<ClaimData[]>(
    `/api/projects/${projectId}/claims?limit=${limit}`
  );
}

export function getContradictions(projectId: string, limit = 100) {
  return request<ContradictionData[]>(
    `/api/projects/${projectId}/contradictions?limit=${limit}`
  );
}
