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
  type ProjectTokenUsage,
} from "@/lib/api";
import { useTypedWebSocket } from "@/hooks/useTypedWebSocket";
import { useBlackboard } from "@/hooks/useBlackboard";
import { parseTS, formatElapsed } from "../_utils/formatters";
import { useEvaluationData } from "./useEvaluationData";
import { useLaneState } from "./useLaneState";
import { usePaperState } from "./usePaperState";

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

// Re-export for backward compatibility
export type { LaneState } from "./useLaneState";

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

  const ws = useTypedWebSocket(projectId);

  // Composed hooks
  const lane = useLaneState(projectId, project?.concurrency, project?.status, ws);
  const evalData = useEvaluationData(projectId, project?.status, ws);
  const paper = usePaperState(projectId, project?.status);

  // Blackboard scoped to active lane
  const blackboardLane = lane.activeLane === null ? undefined : lane.activeLane;
  const blackboard = useBlackboard(ws, projectId, blackboardLane);

  // Initial project load
  useEffect(() => {
    getProject(projectId)
      .then((p) => setProject(p))
      .catch(() => setProject(null))
      .finally(() => setLoading(false));
  }, [projectId]);

  // 30s polling for project status
  useEffect(() => {
    const timer = setInterval(() => {
      getProject(projectId)
        .then((p) => setProject((prev) => prev ? { ...prev, phase: p.phase, status: p.status, updated_at: p.updated_at } : p))
        .catch(() => {});
    }, 30_000);
    return () => clearInterval(timer);
  }, [projectId]);

  // Core WS subscriptions (agent events, checkpoints, phase changes, topic drift, research completion)
  useEffect(() => {
    if (!ws.subscribe) return;

    const unsubs = [
      ws.subscribe("AgentStarted", (payload) => {
        const eventLane = payload.lane_index;
        if (eventLane !== undefined) {
          lane.setLaneStatuses((prev) =>
            prev.map((ls) =>
              ls.lane === eventLane ? { ...ls, phase: payload.phase, iteration: payload.iteration } : ls
            )
          );
        }
        if (lane.activeLane === null || lane.activeLane === eventLane) {
          setCurrentAgent({ agent: payload.agent, task: payload.task });
          setCurrentIteration(payload.iteration);
          setProject((prev) => prev ? { ...prev, phase: payload.phase } : prev);
        }
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
        setCheckpoint({
          id: payload.id,
          phase: payload.phase,
          summary: payload.summary,
          options: payload.options,
        });
      }),
      ws.subscribe("CheckpointResolved", () => setCheckpoint(null)),
      ws.subscribe("PhaseAdvanced", (payload) => {
        const eventLane = payload.lane_index;
        if (eventLane !== undefined) {
          lane.setLaneStatuses((prev) =>
            prev.map((ls) =>
              ls.lane === eventLane ? { ...ls, phase: payload.phase } : ls
            )
          );
        }
        if (lane.activeLane === null || lane.activeLane === eventLane) {
          setProject((prev) => prev ? { ...prev, phase: payload.phase } : prev);
        }
      }),
      ws.subscribe("TopicDriftWarning", (payload) => {
        setTopicDriftWarning(payload.message);
        setTimeout(() => setTopicDriftWarning(null), 8_000);
      }),
      ws.subscribe("ResearchCompleted", (payload) => {
        setProject((prev) => prev ? { ...prev, status: "completed", phase: "complete" } : prev);
        lane.setLaneState((prev) => prev ? { ...prev, synthesizing: false } : prev);
        if (payload.token_usage) {
          paper.setTokenUsage({
            project_id: payload.token_usage.project_id,
            by_model: payload.token_usage.by_model,
            total_prompt_tokens: payload.token_usage.total_prompt_tokens,
            total_completion_tokens: payload.token_usage.total_completion_tokens,
            total_tokens: payload.token_usage.total_tokens,
            total_cost_usd: payload.token_usage.total_cost_usd,
            total_cost_rmb: payload.token_usage.total_cost_rmb,
            total_calls: payload.token_usage.total_calls,
          });
        } else {
          getProjectUsage(projectId).then(paper.setTokenUsage).catch(() => {});
        }
        getExportedPaper(projectId)
          .then((data) => paper.setPaperContent(data.content))
          .catch(() => {});
      }),
    ];

    return () => unsubs.forEach((fn) => fn());
  }, [ws, projectId, lane.activeLane]);

  // Actions
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

  return {
    // Core state
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
    ws,
    blackboard,

    // Composed state (from sub-hooks)
    ...paper,
    ...lane,
    ...evalData,

    // Setters
    setTopicDriftWarning,
    setShowDeleteConfirm,

    // Actions
    handleToggleRunning,
    handleDelete,
    handleCheckpointResponse,
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
