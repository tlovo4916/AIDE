"use client";

import { useEffect, useState } from "react";
import { getLaneStatuses, type LaneStatus } from "@/lib/api";
import type { useTypedWebSocket } from "@/hooks/useTypedWebSocket";

export interface LaneState {
  total: number;
  completed: number[];
  errors: number[];
  synthesizing: boolean;
}

export function useLaneState(
  projectId: string,
  concurrency: number | undefined,
  projectStatus: string | undefined,
  ws: ReturnType<typeof useTypedWebSocket>,
) {
  const [laneState, setLaneState] = useState<LaneState | null>(null);
  const [activeLane, setActiveLane] = useState<number | "synthesis" | null>(null);
  const [laneStatuses, setLaneStatuses] = useState<LaneStatus[]>([]);

  const isMultiLane = (concurrency ?? 1) > 1;

  // Initial lane setup
  useEffect(() => {
    if (!isMultiLane) return;
    setActiveLane(0);
    getLaneStatuses(projectId).then((statuses) => {
      setLaneStatuses(statuses);
      if (projectStatus === "completed" && statuses.length > 0) {
        setLaneState({
          total: statuses.length,
          completed: statuses.map((s) => s.lane),
          errors: [],
          synthesizing: false,
        });
      }
    }).catch(() => {});
  }, [projectId, isMultiLane, projectStatus]);

  // 30s polling for lane statuses
  useEffect(() => {
    if (activeLane === null) return;
    const timer = setInterval(() => {
      getLaneStatuses(projectId).then(setLaneStatuses).catch(() => {});
    }, 30_000);
    return () => clearInterval(timer);
  }, [projectId, activeLane]);

  // WS subscriptions for lane events
  useEffect(() => {
    if (!ws.subscribe) return;

    const unsubs = [
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
    ];

    return () => unsubs.forEach((fn) => fn());
  }, [ws]);

  return { laneState, setLaneState, activeLane, setActiveLane, laneStatuses, setLaneStatuses };
}
