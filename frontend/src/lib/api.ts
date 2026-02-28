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
      current_phase: string;
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
    current_phase: string;
    status: string;
    created_at: string;
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

export function uploadPaper(file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<{ id: string; filename: string }>("/api/papers", {
    method: "POST",
    headers: {},
    body: form,
  });
}

export function listPapers() {
  return request<{ id: string; filename: string; uploaded_at: string }[]>(
    "/api/papers"
  );
}

export function searchPapers(query: string) {
  return request<
    { id: string; filename: string; relevance: number }[]
  >(`/api/papers/search?q=${encodeURIComponent(query)}`);
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
  response: string
) {
  return request<void>(
    `/api/projects/${projectId}/checkpoints/${checkpointId}/respond`,
    {
      method: "POST",
      body: JSON.stringify({ response }),
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
