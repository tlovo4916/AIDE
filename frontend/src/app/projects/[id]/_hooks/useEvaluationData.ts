"use client";

import { useEffect, useState } from "react";
import {
  getEvaluations,
  getIterationMetrics,
  getClaims,
  getContradictions,
  type EvaluationResult,
  type IterationMetric,
  type ClaimData,
  type ContradictionData,
} from "@/lib/api";
import type { PlannerDecisionPayload } from "@/lib/ws-protocol";
import type { useTypedWebSocket } from "@/hooks/useTypedWebSocket";

export function useEvaluationData(
  projectId: string,
  projectStatus: string | undefined,
  ws: ReturnType<typeof useTypedWebSocket>,
) {
  const [evaluations, setEvaluations] = useState<EvaluationResult[]>([]);
  const [iterationMetrics, setIterationMetrics] = useState<IterationMetric[]>([]);
  const [claims, setClaims] = useState<ClaimData[]>([]);
  const [contradictions, setContradictions] = useState<ContradictionData[]>([]);
  const [plannerDecisions, setPlannerDecisions] = useState<PlannerDecisionPayload[]>([]);

  // Initial load for non-idle projects
  useEffect(() => {
    if (!projectStatus || projectStatus === "idle") return;
    getEvaluations(projectId).then((apiEvals) => {
      setEvaluations((prev) => {
        const apiKeys = new Set(apiEvals.map((e) => `${e.iteration}:${e.phase}`));
        const wsOnly = prev.filter((e) => e.id.startsWith("ws-") && !apiKeys.has(`${e.iteration}:${e.phase}`));
        return [...apiEvals, ...wsOnly];
      });
    }).catch(() => {});
    getIterationMetrics(projectId).then(setIterationMetrics).catch(() => {});
    getClaims(projectId).then(setClaims).catch(() => {});
    getContradictions(projectId).then(setContradictions).catch(() => {});
  }, [projectId, projectStatus]);

  // WS subscriptions for evaluation events
  useEffect(() => {
    if (!ws.subscribe) return;

    const unsubs = [
      ws.subscribe("EvaluationCompleted", (payload) => {
        const p = payload;
        setEvaluations((prev) => {
          const key = `${p.iteration}:${p.phase}`;
          const exists = prev.some((e) => `${e.iteration}:${e.phase}` === key);
          if (exists) return prev;
          return [
            ...prev,
            {
              id: `ws-${p.iteration}-${p.phase}`,
              phase: p.phase,
              iteration: p.iteration,
              composite_score: p.composite_score,
              evaluator_model: p.evaluator_model,
              dimensions: Object.fromEntries(
                Object.entries(p.dimensions).map(([k, v]) => [k, { combined: v as number, weight: 1 }])
              ),
              created_at: new Date().toISOString(),
            },
          ];
        });
        if (p.information_gain !== undefined) {
          setIterationMetrics((prev) => {
            const key = `${p.iteration}:${p.phase}`;
            const exists = prev.some((m) => `${m.iteration}:${m.phase}` === key);
            if (exists) return prev;
            return [
              ...prev,
              {
                id: `ws-metric-${p.iteration}-${p.phase}`,
                phase: p.phase,
                iteration: p.iteration,
                information_gain: p.information_gain ?? null,
                eval_composite: p.composite_score,
                artifact_count_delta: null,
                unique_claim_delta: null,
                metrics: null,
                created_at: new Date().toISOString(),
              },
            ];
          });
        }
      }),
      ws.subscribe("PlannerDecision", (payload) => {
        setPlannerDecisions((prev) => [...prev, payload]);
      }),
    ];

    return () => unsubs.forEach((fn) => fn());
  }, [ws]);

  return { evaluations, iterationMetrics, claims, contradictions, plannerDecisions };
}
