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

export function useBlackboard(ws: WsHook, projectId: string) {
  const [state, setState] = useState<BlackboardState>({
    artifacts: {},
    messages: [],
    challenges: [],
    currentPhase: "",
    isLoading: true,
  });

  // 页面挂载时从 REST 端点加载历史状态（支持刷新后恢复）
  useEffect(() => {
    if (!projectId) return;
    getBlackboard(projectId)
      .then((snapshot) => {
        setState((prev) => ({
          ...prev,
          artifacts: snapshot.artifacts as Record<string, Artifact[]>,
          challenges: snapshot.challenges,
          messages: snapshot.messages,
          isLoading: false,
        }));
      })
      .catch(() => {
        setState((prev) => ({ ...prev, isLoading: false }));
      });
  }, [projectId]);

  const initialLoadDone = useRef(false);

  useEffect(() => {
    if (ws.status === "connected" && !initialLoadDone.current) {
      initialLoadDone.current = true;
    }
  }, [ws.status]);

  const handleArtifactUpdated = useCallback(
    (payload: ArtifactUpdatedPayload) => {
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
    []
  );

  const handleChallengeRaised = useCallback(
    (payload: ChallengeRaisedPayload) => {
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
    []
  );

  const handleChallengeResolved = useCallback(
    (payload: ChallengeResolvedPayload) => {
      setState((prev) => ({
        ...prev,
        challenges: prev.challenges.map((c) =>
          c.id === payload.id ? { ...c, resolved: true } : c
        ),
      }));
    },
    []
  );

  const handlePhaseAdvanced = useCallback(
    (payload: PhaseAdvancedPayload) => {
      setState((prev) => ({ ...prev, currentPhase: payload.phase }));
    },
    []
  );

  const handleAgentActivity = useCallback(
    (payload: { agent?: string; action?: string; timestamp?: string }) => {
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
    []
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
