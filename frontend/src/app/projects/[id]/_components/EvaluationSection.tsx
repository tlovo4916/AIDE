"use client";

import { useState, useMemo } from "react";
import { Activity, GitBranch, AlertTriangle, Brain } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  AreaChart,
  Area,
} from "recharts";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useLocale } from "@/contexts/LocaleContext";
import type { EvaluationResult, IterationMetric, ClaimData, ContradictionData } from "@/lib/api";
import type { PlannerDecisionPayload } from "@/lib/ws-protocol";

interface EvaluationSectionProps {
  projectId: string;
  evaluations: EvaluationResult[];
  iterationMetrics: IterationMetric[];
  claims: ClaimData[];
  contradictions: ContradictionData[];
  plannerDecisions: PlannerDecisionPayload[];
  currentPhase: string;
}

// ─── Constants ──────────────────────────────────────────────────

const PHASE_COLORS: Record<string, string> = {
  explore: "#10b981",
  hypothesize: "#3b82f6",
  evidence: "#06b6d4",
  compose: "#f59e0b",
  synthesize: "#8b5cf6",
  complete: "#22c55e",
};

const AGENT_COLORS: Record<string, string> = {
  director: "#10b981",
  scientist: "#3b82f6",
  librarian: "#06b6d4",
  writer: "#f59e0b",
  critic: "#ef4444",
  synthesizer: "#8b5cf6",
};

const CONFIDENCE_STYLES: Record<string, { color: string; bg: string; border: string }> = {
  strong: { color: "text-green-500", bg: "bg-green-500/10", border: "border-green-500/30" },
  moderate: { color: "text-amber-500", bg: "bg-amber-500/10", border: "border-amber-500/30" },
  tentative: { color: "text-slate-400", bg: "bg-slate-400/10", border: "border-slate-400/30" },
};

const STATUS_STYLES: Record<string, { color: string; bg: string; border: string; label: string }> = {
  unresolved: { color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/30", label: "Unresolved" },
  resolved: { color: "text-green-400", bg: "bg-green-500/10", border: "border-green-500/30", label: "Resolved" },
  accepted_as_limitation: { color: "text-slate-400", bg: "bg-slate-400/10", border: "border-slate-400/30", label: "Limitation" },
};

type TabKey = "quality" | "decisions" | "contradictions" | "claims";

// ─── Custom Tooltip ─────────────────────────────────────────────

function ChartTooltip({
  active,
  payload,
  label,
  formatter,
}: {
  active?: boolean;
  payload?: { value: number; name?: string; color?: string }[];
  label?: string | number;
  formatter?: (value: number) => string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-aide-border bg-aide-bg-secondary px-3 py-2 shadow-lg">
      <p className="mb-1 text-xs font-medium text-aide-text-muted">
        Iteration {label}
      </p>
      {payload.map((entry, i) => (
        <p key={i} className="text-sm font-semibold text-aide-text-primary">
          <span
            className="mr-1.5 inline-block h-2 w-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          {formatter ? formatter(entry.value) : entry.value.toFixed(2)}
        </p>
      ))}
    </div>
  );
}

// ─── Main Component ─────────────────────────────────────────────

export function EvaluationSection({
  evaluations,
  iterationMetrics: _iterationMetrics,
  claims,
  contradictions,
  plannerDecisions,
}: EvaluationSectionProps) {
  const { t } = useLocale();
  const [activeTab, setActiveTab] = useState<TabKey>("quality");

  const tabs: { key: TabKey; labelKey: Parameters<typeof t>[0]; icon: typeof Activity }[] = [
    { key: "quality", labelKey: "section.qualityDashboard", icon: Activity },
    { key: "decisions", labelKey: "section.plannerDecisions", icon: Brain },
    { key: "contradictions", labelKey: "section.contradictions", icon: AlertTriangle },
    { key: "claims", labelKey: "section.claims", icon: GitBranch },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Tab Navigation */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {tabs.map(({ key, labelKey, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-all duration-200 ${
              activeTab === key
                ? "bg-aide-accent-blue/15 text-aide-accent-blue shadow-sm"
                : "text-aide-text-muted hover:bg-aide-bg-tertiary hover:text-aide-text-secondary"
            }`}
          >
            <Icon className="h-4 w-4" />
            {t(labelKey)}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "quality" && (
        <QualityDashboard evaluations={evaluations} iterationMetrics={_iterationMetrics} />
      )}
      {activeTab === "decisions" && (
        <PlannerDecisionsPanel decisions={plannerDecisions} />
      )}
      {activeTab === "contradictions" && (
        <ContradictionsPanel contradictions={contradictions} claims={claims} />
      )}
      {activeTab === "claims" && (
        <ClaimsPanel claims={claims} />
      )}
    </div>
  );
}

// ─── Quality Dashboard ──────────────────────────────────────────

function QualityDashboard({ evaluations, iterationMetrics }: { evaluations: EvaluationResult[]; iterationMetrics: IterationMetric[] }) {
  const { t } = useLocale();

  const sortedEvals = useMemo(
    () => [...evaluations].sort((a, b) => a.iteration - b.iteration),
    [evaluations]
  );

  const lineData = useMemo(
    () =>
      sortedEvals.map((ev) => ({
        iteration: ev.iteration,
        composite_score: ev.composite_score,
        phase: ev.phase,
        fill: PHASE_COLORS[ev.phase.toLowerCase()] ?? "#818cf8",
      })),
    [sortedEvals]
  );

  const latestEval = sortedEvals.length > 0 ? sortedEvals[sortedEvals.length - 1] : null;

  // Compute dynamic scale from actual data
  const scoreMax = useMemo(() => {
    if (sortedEvals.length === 0) return 10;
    const allScores = sortedEvals.map((e) => e.composite_score);
    const allDimValues = sortedEvals.flatMap((e) =>
      Object.values(e.dimensions).map((d) =>
        typeof d === "number" ? d : (d as { combined: number }).combined ?? 0
      )
    );
    const maxVal = Math.max(...allScores, ...allDimValues, 1);
    // Round up to nearest nice number: 1, 5, 10, 20, 100
    if (maxVal <= 1) return 1;
    if (maxVal <= 5) return 5;
    if (maxVal <= 10) return 10;
    if (maxVal <= 20) return 20;
    return Math.ceil(maxVal / 10) * 10;
  }, [sortedEvals]);

  const radarData = useMemo(() => {
    if (!latestEval) return [];
    return Object.entries(latestEval.dimensions).map(([key, dim]) => ({
      dimension: key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      value: typeof dim === "number" ? dim : (dim as { combined: number }).combined ?? 0,
      fullMark: scoreMax,
    }));
  }, [latestEval, scoreMax]);

  const areaData = useMemo(
    () =>
      [...iterationMetrics]
        .filter((m) => m.information_gain != null)
        .sort((a, b) => a.iteration - b.iteration)
        .map((m) => ({
          iteration: m.iteration,
          information_gain: m.information_gain,
        })),
    [iterationMetrics]
  );

  if (evaluations.length === 0) {
    return (
      <EmptyState
        icon={Activity}
        title={t("empty.noEvaluations")}
        hint={t("empty.noEvaluationsHint")}
      />
    );
  }

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Composite Score Line Chart — full width */}
      <Card>
        <CardContent className="py-5">
          <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-aide-text-muted">
            {t("section.compositeScore")}
          </h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={lineData} margin={{ top: 8, right: 16, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--aide-border)" opacity={0.5} />
              <XAxis
                dataKey="iteration"
                tick={{ fontSize: 11, fill: "var(--aide-text-muted)" }}
                axisLine={{ stroke: "var(--aide-border)" }}
                tickLine={false}
              />
              <YAxis
                domain={[0, scoreMax]}
                tick={{ fontSize: 11, fill: "var(--aide-text-muted)" }}
                axisLine={{ stroke: "var(--aide-border)" }}
                tickLine={false}
              />
              <RechartsTooltip
                content={({ active, payload, label }) => (
                  <ChartTooltip
                    active={active}
                    payload={payload?.map((p) => ({
                      value: p.value as number,
                      color: (p.payload as { fill: string }).fill,
                    }))}
                    label={label}
                    formatter={(v) => `${v.toFixed(1)} / ${scoreMax}`}
                  />
                )}
              />
              <Line
                type="monotone"
                dataKey="composite_score"
                stroke="#818cf8"
                strokeWidth={2.5}
                dot={({ cx, cy, payload }) => (
                  <circle
                    key={`dot-${payload.iteration}`}
                    cx={cx}
                    cy={cy}
                    r={5}
                    fill={payload.fill}
                    stroke="#fff"
                    strokeWidth={2}
                  />
                )}
                activeDot={{ r: 7, stroke: "#818cf8", strokeWidth: 2 }}
              />
            </LineChart>
          </ResponsiveContainer>
          {/* Phase legend */}
          <div className="mt-3 flex flex-wrap items-center gap-3">
            {Object.entries(PHASE_COLORS).map(([phase, color]) => (
              <span key={phase} className="inline-flex items-center gap-1.5 text-xs text-aide-text-muted">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
                {phase.charAt(0).toUpperCase() + phase.slice(1)}
              </span>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Radar + Area — side by side */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Dimension Radar */}
        <Card>
          <CardContent className="py-5">
            <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-aide-text-muted">
              {t("section.dimensionRadar")}
            </h3>
            {radarData.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="75%">
                  <PolarGrid stroke="var(--aide-border)" opacity={0.5} />
                  <PolarAngleAxis
                    dataKey="dimension"
                    tick={{ fontSize: 10, fill: "var(--aide-text-muted)" }}
                  />
                  <PolarRadiusAxis
                    angle={30}
                    domain={[0, scoreMax]}
                    tick={{ fontSize: 9, fill: "var(--aide-text-muted)" }}
                    axisLine={false}
                  />
                  <Radar
                    dataKey="value"
                    stroke="#818cf8"
                    fill="#818cf8"
                    fillOpacity={0.25}
                    strokeWidth={2}
                  />
                  <RechartsTooltip
                    content={({ active, payload }) => (
                      <ChartTooltip
                        active={active}
                        payload={payload?.map((p) => ({
                          value: p.value as number,
                          color: "#818cf8",
                        }))}
                        label={payload?.[0]?.payload?.dimension}
                        formatter={(v) => `${v.toFixed(1)} / ${scoreMax}`}
                      />
                    )}
                  />
                </RadarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-[280px] items-center justify-center text-sm text-aide-text-muted">
                No dimension data
              </div>
            )}
          </CardContent>
        </Card>

        {/* Information Gain Area Chart */}
        <Card>
          <CardContent className="py-5">
            <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-aide-text-muted">
              {t("section.informationGain")}
            </h3>
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={areaData} margin={{ top: 8, right: 16, left: 0, bottom: 4 }}>
                <defs>
                  <linearGradient id="gainGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#818cf8" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#4f46e5" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--aide-border)" opacity={0.5} />
                <XAxis
                  dataKey="iteration"
                  tick={{ fontSize: 11, fill: "var(--aide-text-muted)" }}
                  axisLine={{ stroke: "var(--aide-border)" }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "var(--aide-text-muted)" }}
                  axisLine={{ stroke: "var(--aide-border)" }}
                  tickLine={false}
                />
                <RechartsTooltip
                  content={({ active, payload, label }) => (
                    <ChartTooltip
                      active={active}
                      payload={payload?.map((p) => ({
                        value: p.value as number,
                        color: "#6366f1",
                      }))}
                      label={label}
                      formatter={(v) => v.toFixed(4)}
                    />
                  )}
                />
                <Area
                  type="monotone"
                  dataKey="information_gain"
                  stroke="#6366f1"
                  strokeWidth={2}
                  fill="url(#gainGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ─── Planner Decisions Panel ────────────────────────────────────

function PlannerDecisionsPanel({
  decisions,
}: {
  decisions: PlannerDecisionPayload[];
}) {
  const { t } = useLocale();

  const sorted = useMemo(
    () => [...decisions].sort((a, b) => b.iteration - a.iteration),
    [decisions]
  );

  if (sorted.length === 0) {
    return (
      <EmptyState
        icon={Brain}
        title={t("empty.noDecisions")}
        hint=""
      />
    );
  }

  return (
    <div className="space-y-3 animate-slide-up">
      {sorted.map((decision, idx) => {
        const agentColor = AGENT_COLORS[decision.chosen_agent.toLowerCase()] ?? "#818cf8";
        const candidates = decision.candidates ?? [];
        const maxScore = Math.max(...candidates.map((c) => c.score), 0.01);

        return (
          <Card key={`${decision.iteration}-${idx}`}>
            <CardContent className="py-4">
              <div className="flex items-start gap-3">
                {/* Iteration badge */}
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-aide-accent-blue/10 text-xs font-bold text-aide-accent-blue">
                  #{decision.iteration}
                </div>

                <div className="min-w-0 flex-1">
                  {/* Chosen agent + phase */}
                  <div className="flex items-center gap-2">
                    <span
                      className="text-sm font-bold"
                      style={{ color: agentColor }}
                    >
                      {decision.chosen_agent.charAt(0).toUpperCase() +
                        decision.chosen_agent.slice(1)}
                    </span>
                    {decision.phase && (
                      <Badge variant="phase">{decision.phase}</Badge>
                    )}
                  </div>

                  {/* Rationale */}
                  <p className="mt-1 text-xs leading-relaxed text-aide-text-secondary">
                    {decision.rationale}
                  </p>

                  {/* Candidate scores */}
                  {candidates.length > 0 && (
                    <div className="mt-3 space-y-1.5">
                      {[...candidates]
                        .sort((a, b) => b.score - a.score)
                        .map((cand) => {
                          const color = AGENT_COLORS[cand.agent.toLowerCase()] ?? "#818cf8";
                          const widthPct = Math.max((cand.score / maxScore) * 100, 2);
                          const isChosen = cand.agent.toLowerCase() === decision.chosen_agent.toLowerCase();

                          return (
                            <div key={cand.agent} className="flex items-center gap-2">
                              <span
                                className={`w-20 truncate text-[11px] ${
                                  isChosen ? "font-semibold" : "font-normal text-aide-text-muted"
                                }`}
                                style={isChosen ? { color } : undefined}
                              >
                                {cand.agent}
                              </span>
                              <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-aide-bg-tertiary">
                                <div
                                  className="absolute inset-y-0 left-0 rounded-full transition-all duration-300"
                                  style={{
                                    width: `${widthPct}%`,
                                    backgroundColor: color,
                                    opacity: isChosen ? 1 : 0.5,
                                  }}
                                />
                              </div>
                              <span className="w-8 text-right text-[11px] text-aide-text-muted">
                                {cand.score.toFixed(2)}
                              </span>
                            </div>
                          );
                        })}
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

// ─── Contradictions Panel ───────────────────────────────────────

function ContradictionsPanel({
  contradictions,
  claims,
}: {
  contradictions: ContradictionData[];
  claims: ClaimData[];
}) {
  const { t } = useLocale();

  const claimsMap = useMemo(() => {
    const map = new Map<string, ClaimData>();
    for (const c of claims) map.set(c.claim_id, c);
    return map;
  }, [claims]);

  if (contradictions.length === 0) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title={t("empty.noContradictions")}
        hint=""
      />
    );
  }

  return (
    <div className="space-y-4 animate-slide-up">
      {contradictions.map((contradiction) => {
        const claimA = claimsMap.get(contradiction.claim_a_id);
        const claimB = claimsMap.get(contradiction.claim_b_id);
        const statusStyle = STATUS_STYLES[contradiction.status] ?? STATUS_STYLES.unresolved;

        return (
          <Card key={contradiction.id}>
            <CardContent className="py-4">
              {/* Header: status badge + confidence */}
              <div className="mb-3 flex items-center justify-between">
                <span
                  className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${statusStyle.color} ${statusStyle.bg} ${statusStyle.border}`}
                >
                  {statusStyle.label}
                </span>
                <span className="text-xs text-aide-text-muted">
                  {(contradiction.confidence * 100).toFixed(0)}% confidence
                </span>
              </div>

              {/* Claim A vs Claim B */}
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-aide-border/60 bg-aide-bg-primary/50 p-3">
                  <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-aide-text-muted">
                    Claim A
                  </span>
                  <p className="text-xs leading-relaxed text-aide-text-primary">
                    {claimA?.text ?? contradiction.claim_a_id}
                  </p>
                </div>
                <div className="rounded-lg border border-aide-border/60 bg-aide-bg-primary/50 p-3">
                  <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-aide-text-muted">
                    Claim B
                  </span>
                  <p className="text-xs leading-relaxed text-aide-text-primary">
                    {claimB?.text ?? contradiction.claim_b_id}
                  </p>
                </div>
              </div>

              {/* Confidence bar */}
              <div className="mt-3">
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-aide-bg-tertiary">
                  <div
                    className="h-full rounded-full transition-all duration-300"
                    style={{
                      width: `${contradiction.confidence * 100}%`,
                      backgroundColor:
                        contradiction.status === "unresolved"
                          ? "#ef4444"
                          : contradiction.status === "resolved"
                            ? "#22c55e"
                            : "#94a3b8",
                    }}
                  />
                </div>
              </div>

              {/* Evidence details */}
              {contradiction.evidence && Object.keys(contradiction.evidence).length > 0 && (
                <p className="mt-2 text-xs text-aide-text-secondary">
                  {(contradiction.evidence as Record<string, unknown>).explanation as string ??
                   JSON.stringify(contradiction.evidence).slice(0, 200)}
                </p>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

// ─── Claims Panel ───────────────────────────────────────────────

function ClaimsPanel({ claims }: { claims: ClaimData[] }) {
  const { t } = useLocale();
  const [filterConfidence, setFilterConfidence] = useState<string>("all");

  const filtered = useMemo(() => {
    if (filterConfidence === "all") return claims;
    return claims.filter((c) => c.confidence === filterConfidence);
  }, [claims, filterConfidence]);

  if (claims.length === 0) {
    return (
      <EmptyState
        icon={GitBranch}
        title={t("empty.noClaims")}
        hint=""
      />
    );
  }

  const confidenceOptions = [
    { key: "all", label: "All" },
    { key: "strong", label: "Strong" },
    { key: "moderate", label: "Moderate" },
    { key: "tentative", label: "Tentative" },
  ];

  return (
    <div className="space-y-4 animate-slide-up">
      {/* Filter bar */}
      <div className="flex items-center gap-2">
        {confidenceOptions.map((opt) => (
          <button
            key={opt.key}
            onClick={() => setFilterConfidence(opt.key)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-all duration-200 ${
              filterConfidence === opt.key
                ? "bg-aide-accent-blue/15 text-aide-accent-blue"
                : "text-aide-text-muted hover:bg-aide-bg-tertiary hover:text-aide-text-secondary"
            }`}
          >
            {opt.label}
            {opt.key !== "all" && (
              <span className="ml-1 text-aide-text-muted">
                ({claims.filter((c) => c.confidence === opt.key).length})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Claims table */}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-aide-border">
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-aide-text-muted">
                  Text
                </th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-aide-text-muted">
                  Source
                </th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-aide-text-muted">
                  Confidence
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-aide-border/50">
              {filtered.map((claim) => {
                const style = CONFIDENCE_STYLES[claim.confidence] ?? CONFIDENCE_STYLES.tentative;
                return (
                  <tr
                    key={claim.claim_id}
                    className="transition-colors hover:bg-aide-bg-tertiary/50"
                  >
                    <td className="max-w-md px-4 py-3">
                      <p className="truncate text-xs text-aide-text-primary" title={claim.text}>
                        {claim.text}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs text-aide-text-secondary">{claim.source_artifact}</span>
                    </td>
                    <td className="px-4 py-3">
                      <Badge
                        className={`${style.color} ${style.bg} ${style.border}`}
                      >
                        {claim.confidence}
                      </Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {filtered.length === 0 && (
          <div className="py-8 text-center text-xs text-aide-text-muted">
            No claims match the selected filter.
          </div>
        )}
      </Card>
    </div>
  );
}

// ─── Shared Components ──────────────────────────────────────────

function EmptyState({
  icon: Icon,
  title,
  hint,
}: {
  icon: typeof Activity;
  title: string;
  hint: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-aide-border py-16 animate-fade-in">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-aide-bg-tertiary">
        <Icon className="h-6 w-6 text-aide-text-muted" />
      </div>
      <p className="text-sm font-medium text-aide-text-secondary">{title}</p>
      {hint && (
        <p className="mt-1 text-xs text-aide-text-muted">{hint}</p>
      )}
    </div>
  );
}

