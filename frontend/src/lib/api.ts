const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

// --- Projects ---

export interface CreateProjectPayload {
  name: string;
  research_topic: string;
  paper_ids?: string[];
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

// --- Papers ---

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

// --- Checkpoints ---

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

// --- Settings ---

export function getSettings() {
  return request<Record<string, unknown>>("/api/settings");
}

export function updateSettings(settings: Record<string, unknown>) {
  return request<void>("/api/settings", {
    method: "PUT",
    body: JSON.stringify(settings),
  });
}

// --- Blackboard ---

export function getBlackboard(projectId: string) {
  return request<{
    artifacts: Record<string, { id: string; type: string; data: Record<string, unknown> }[]>;
    challenges: { id: string; from: string; message: string; resolved: boolean }[];
    messages: { id: string; role: string; content: string; timestamp: string }[];
  }>(`/api/projects/${projectId}/blackboard`);
}

// --- Token Usage ---

export function getTokenUsage(projectId?: string) {
  const qs = projectId ? `?project_id=${projectId}` : "";
  return request<{
    total_tokens: number;
    prompt_tokens: number;
    completion_tokens: number;
    cost_usd: number;
  }>(`/api/usage${qs}`);
}
