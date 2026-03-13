"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getProject,
  respondToCheckpoint,
  startProject,
  pauseProject,
  resumeProject,
  deleteProject,
  getExportedPaper,
  getProjectUsage,
  getCitationGraph,
  type ProjectTokenUsage,
  type CitationGraphData,
} from "@/lib/api";
import { useTypedWebSocket } from "@/hooks/useTypedWebSocket";
import { useBlackboard } from "@/hooks/useBlackboard";
import { parseTS, formatElapsed } from "../_utils/formatters";

export interface Project {
  id: string;
  name: string;
  research_topic: string;
  concurrency?: number;
  phase: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface AgentEvent {
  id: string;
  agent: string;
  action: string;
  timestamp: string;
}

export interface Checkpoint {
  id: string;
  phase: string;
  summary: string;
  options: { label: string; value: string }[];
}

export interface LaneState {
  total: number;
  completed: number[];
  errors: number[];
  synthesizing: boolean;
}

export function useProjectState(projectId: string) {
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [agentEvents, setAgentEvents] = useState<AgentEvent[]>([]);
  const [currentAgent, setCurrentAgent] = useState<{ agent: string; task: string } | null>(null);
  const [currentIteration, setCurrentIteration] = useState<number>(0);
  const [topicDriftWarning, setTopicDriftWarning] = useState<string | null>(null);
  const [checkpoint, setCheckpoint] = useState<Checkpoint | null>(null);
  const [checkpointLoading, setCheckpointLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [paperContent, setPaperContent] = useState<string | null>(null);
  const [tokenUsage, setTokenUsage] = useState<ProjectTokenUsage | null>(null);
  const [citationGraph, setCitationGraph] = useState<CitationGraphData | null>(null);
  const [laneState, setLaneState] = useState<LaneState | null>(null);

  const ws = useTypedWebSocket(projectId);
  const blackboard = useBlackboard(ws, projectId);

  // Initial load
  useEffect(() => {
    getProject(projectId)
      .then((p) => {
        setProject(p);
        if (p.status === "completed") {
          getProjectUsage(projectId).then(setTokenUsage).catch(() => {});
          getExportedPaper(projectId)
            .then((data) => setPaperContent(data.content))
            .catch(() => {});
        }
      })
      .catch(() => setProject(null))
      .finally(() => setLoading(false));
  }, [projectId]);

  // 30s polling
  useEffect(() => {
    const timer = setInterval(() => {
      getProject(projectId)
        .then((p) => setProject((prev) => prev ? { ...prev, phase: p.phase, status: p.status, updated_at: p.updated_at } : p))
        .catch(() => {});
    }, 30_000);
    return () => clearInterval(timer);
  }, [projectId]);

  // WebSocket subscriptions
  useEffect(() => {
    if (!ws.subscribe) return;

    const unsubs = [
      ws.subscribe("AgentStarted", (payload) => {
        setCurrentAgent({ agent: payload.agent, task: payload.task });
        setCurrentIteration(payload.iteration);
        setProject((prev) => prev ? { ...prev, phase: payload.phase } : prev);
      }),
      ws.subscribe("AgentActivity", (payload) => {
        setCurrentAgent(null);
        const meta = payload.metadata as Record<string, unknown> | undefined;
        if (typeof meta?.iteration === "number") setCurrentIteration(meta.iteration);
        setAgentEvents((prev) => [
          { id: crypto.randomUUID(), ...payload } as AgentEvent,
          ...prev,
        ]);
      }),
      ws.subscribe("AgentError", () => setCurrentAgent(null)),
      ws.subscribe("CheckpointCreated", (payload) => {
        setCurrentAgent(null);
        setCheckpoint(payload as unknown as Checkpoint);
      }),
      ws.subscribe("CheckpointResolved", () => setCheckpoint(null)),
      ws.subscribe("PhaseAdvanced", (payload) => {
        setProject((prev) => prev ? { ...prev, phase: payload.phase } : prev);
      }),
      ws.subscribe("TopicDriftWarning", (payload) => {
        setTopicDriftWarning(payload.message);
        setTimeout(() => setTopicDriftWarning(null), 8_000);
      }),
      ws.subscribe("LanesStarted", (payload) => {
        setLaneState({ total: payload.num_lanes, completed: [], errors: [], synthesizing: false });
      }),
      ws.subscribe("LaneCompleted", (payload) => {
        setLaneState((prev) => {
          if (!prev) return prev;
          const completed = [...prev.completed];
          const errors = [...prev.errors];
          if (payload.error) {
            if (!errors.includes(payload.lane)) errors.push(payload.lane);
          } else {
            if (!completed.includes(payload.lane)) completed.push(payload.lane);
          }
          return { ...prev, completed, errors };
        });
      }),
      ws.subscribe("SynthesisStarted", () => {
        setLaneState((prev) => prev ? { ...prev, synthesizing: true } : prev);
      }),
      ws.subscribe("ResearchCompleted", (payload) => {
        setProject((prev) => prev ? { ...prev, status: "completed", phase: "complete" } : prev);
        if (payload.token_usage) {
          setTokenUsage(payload.token_usage as unknown as ProjectTokenUsage);
        } else {
          getProjectUsage(projectId).then(setTokenUsage).catch(() => {});
        }
        getExportedPaper(projectId)
          .then((data) => setPaperContent(data.content))
          .catch(() => {});
      }),
    ];

    return () => unsubs.forEach((fn) => fn());
  }, [ws, projectId]);

  const handleToggleRunning = useCallback(async () => {
    if (!project || actionLoading) return;
    setActionLoading(true);
    try {
      if (project.status === "running") {
        await pauseProject(projectId);
        setProject((prev) => (prev ? { ...prev, status: "paused" } : prev));
      } else {
        const fn = project.status === "paused" ? resumeProject : startProject;
        await fn(projectId);
        setProject((prev) => (prev ? { ...prev, status: "running" } : prev));
      }
    } catch (err) {
      console.error("Failed to toggle project state", err);
    } finally {
      setActionLoading(false);
    }
  }, [project, projectId, actionLoading]);

  const handleDelete = useCallback(async () => {
    setDeleting(true);
    try {
      await deleteProject(projectId);
      return true;
    } finally {
      setDeleting(false);
    }
  }, [projectId]);

  const handleCheckpointResponse = useCallback(
    async (value: string) => {
      if (!checkpoint) return;
      setCheckpointLoading(true);
      try {
        await respondToCheckpoint(projectId, checkpoint.id, value);
        setCheckpoint(null);
      } finally {
        setCheckpointLoading(false);
      }
    },
    [projectId, checkpoint]
  );

  const loadCitationGraph = useCallback(async () => {
    try {
      const data = await getCitationGraph(projectId);
      if (data.total_papers > 0) {
        setCitationGraph(data);
        return data;
      }
    } catch { /* no graph yet */ }
    return null;
  }, [projectId]);

  const loadTokenUsage = useCallback(async () => {
    try {
      const usage = await getProjectUsage(projectId);
      setTokenUsage(usage);
      return usage;
    } catch { return null; }
  }, [projectId]);

  return {
    // State
    project,
    loading,
    agentEvents,
    currentAgent,
    currentIteration,
    topicDriftWarning,
    checkpoint,
    checkpointLoading,
    actionLoading,
    showDeleteConfirm,
    deleting,
    paperContent,
    tokenUsage,
    citationGraph,
    laneState,
    ws,
    blackboard,

    // Setters
    setTopicDriftWarning,
    setShowDeleteConfirm,
    setPaperContent,
    setTokenUsage,

    // Actions
    handleToggleRunning,
    handleDelete,
    handleCheckpointResponse,
    loadCitationGraph,
    loadTokenUsage,
  };
}

export function useElapsedTime(since: string | undefined, active: boolean) {
  const [elapsed, setElapsed] = useState("");
  useEffect(() => {
    if (!since) { setElapsed(""); return; }
    const update = () => {
      const ms = Date.now() - parseTS(since).getTime();
      setElapsed(formatElapsed(Math.max(0, ms)));
    };
    update();
    if (!active) return;
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [since, active]);
  return elapsed;
}
