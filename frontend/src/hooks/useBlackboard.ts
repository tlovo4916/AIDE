"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import type {
  ArtifactUpdatedPayload,
  ChallengeRaisedPayload,
  ChallengeResolvedPayload,
  PhaseAdvancedPayload,
  WSPushEvent,
  WSPushPayloadMap,
} from "@/lib/ws-protocol";
import { getBlackboard } from "@/lib/api";

interface Artifact {
  id: string;
  type: string;
  data: Record<string, unknown>;
}

interface Challenge {
  id: string;
  from: string;
  message: string;
  resolved: boolean;
}

interface Message {
  id: string;
  role: string;
  content: string;
  timestamp: string;
}

interface BlackboardState {
  artifacts: Record<string, Artifact[]>;
  messages: Message[];
  challenges: Challenge[];
  currentPhase: string;
  isLoading: boolean;
}

type WsHook = {
  status: string;
  subscribe: <E extends WSPushEvent>(
    event: E,
    callback: (payload: WSPushPayloadMap[E]) => void
  ) => () => void;
  send: (event: string, payload: unknown, requestId?: string) => void;
};

export function useBlackboard(ws: WsHook, projectId: string, lane?: number | "synthesis") {
  const [state, setState] = useState<BlackboardState>({
    artifacts: {},
    messages: [],
    challenges: [],
    currentPhase: "",
    isLoading: true,
  });

  // Convert lane to API param: "synthesis" → no lane (reads main workspace)
  const apiLane = typeof lane === "number" ? lane : undefined;

  // 页面挂载时从 REST 端点加载历史状态（支持刷新后恢复）
  // Uses a cancelled flag to prevent stale fetches from overwriting fresh data
  // (e.g., when apiLane changes rapidly from undefined→0 on multi-lane project load)
  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    // Clear artifacts to prevent showing stale data from previous lane
    setState({ artifacts: {}, messages: [], challenges: [], currentPhase: "", isLoading: true });
    getBlackboard(projectId, apiLane)
      .then((snapshot) => {
        if (cancelled) return;
        setState({
          artifacts: snapshot.artifacts as Record<string, Artifact[]>,
          challenges: snapshot.challenges,
          messages: snapshot.messages,
          currentPhase: "",
          isLoading: false,
        });
      })
      .catch(() => {
        if (cancelled) return;
        setState((prev) => ({ ...prev, isLoading: false }));
      });
    return () => { cancelled = true; };
  }, [projectId, apiLane]);

  const initialLoadDone = useRef(false);

  useEffect(() => {
    if (ws.status === "connected" && !initialLoadDone.current) {
      initialLoadDone.current = true;
    }
  }, [ws.status]);

  // Filter WS events by lane_index: when viewing a specific lane, only accept
  // events from that lane; when viewing synthesis/main, only accept events
  // without lane_index.
  const shouldAcceptEvent = useCallback(
    (payload: Record<string, unknown>): boolean => {
      const eventLane = payload.lane_index as number | undefined;
      if (typeof lane === "number") return eventLane === lane;
      // synthesis or no lane selected → accept events without lane_index
      return eventLane === undefined || eventLane === null;
    },
    [lane]
  );

  const handleArtifactUpdated = useCallback(
    (payload: ArtifactUpdatedPayload) => {
      if (!shouldAcceptEvent(payload as unknown as Record<string, unknown>)) return;
      setState((prev) => {
        const type = payload.artifact_type;
        const existing = prev.artifacts[type] ?? [];

        let updated: Artifact[];
        if (payload.action === "created") {
          updated = [
            ...existing,
            {
              id: payload.artifact_id,
              type,
              data: payload.data,
            },
          ];
        } else if (payload.action === "updated") {
          updated = existing.map((a) =>
            a.id === payload.artifact_id
              ? { ...a, data: { ...a.data, ...payload.data } }
              : a
          );
        } else {
          updated = existing.filter((a) => a.id !== payload.artifact_id);
        }

        return {
          ...prev,
          artifacts: { ...prev.artifacts, [type]: updated },
        };
      });
    },
    [shouldAcceptEvent]
  );

  const handleChallengeRaised = useCallback(
    (payload: ChallengeRaisedPayload) => {
      if (!shouldAcceptEvent(payload as unknown as Record<string, unknown>)) return;
      setState((prev) => ({
        ...prev,
        challenges: [
          ...prev.challenges,
          {
            id: payload.id,
            from: payload.from,
            message: payload.message,
            resolved: false,
          },
        ],
      }));
    },
    [shouldAcceptEvent]
  );

  const handleChallengeResolved = useCallback(
    (payload: ChallengeResolvedPayload) => {
      if (!shouldAcceptEvent(payload as unknown as Record<string, unknown>)) return;
      setState((prev) => ({
        ...prev,
        challenges: prev.challenges.map((c) =>
          c.id === payload.id ? { ...c, resolved: true } : c
        ),
      }));
    },
    [shouldAcceptEvent]
  );

  const handlePhaseAdvanced = useCallback(
    (payload: PhaseAdvancedPayload) => {
      if (!shouldAcceptEvent(payload as unknown as Record<string, unknown>)) return;
      setState((prev) => ({ ...prev, currentPhase: payload.phase }));
    },
    [shouldAcceptEvent]
  );

  const handleAgentActivity = useCallback(
    (payload: { agent?: string; action?: string; timestamp?: string }) => {
      if (!shouldAcceptEvent(payload as unknown as Record<string, unknown>)) return;
      if (!payload.agent || !payload.action) return;
      setState((prev) => ({
        ...prev,
        messages: [
          ...prev.messages,
          {
            id: crypto.randomUUID(),
            role: payload.agent!,
            content: payload.action!,
            timestamp: payload.timestamp ?? new Date().toISOString(),
          },
        ],
      }));
    },
    [shouldAcceptEvent]
  );

  useEffect(() => {
    const unsubs = [
      ws.subscribe("ArtifactUpdated", handleArtifactUpdated),
      ws.subscribe("ChallengeRaised", handleChallengeRaised),
      ws.subscribe("ChallengeResolved", handleChallengeResolved),
      ws.subscribe("PhaseAdvanced", handlePhaseAdvanced),
      ws.subscribe("AgentActivity", handleAgentActivity),
    ];
    return () => unsubs.forEach((fn) => fn());
  }, [
    ws,
    handleArtifactUpdated,
    handleChallengeRaised,
    handleChallengeResolved,
    handlePhaseAdvanced,
    handleAgentActivity,
  ]);

  return state;
}
