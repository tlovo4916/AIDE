"use client";

import { useState } from "react";
import {
  Play,
  Pause,
  Loader2,
  CheckCircle2,
  Clock,
  Calendar,
  TrendingUp,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Markdown } from "@/components/ui/markdown";
import { useLocale } from "@/contexts/LocaleContext";
import type { I18nKey } from "@/lib/i18n";
import { PHASES, formatDateTime, formatDateTimeFull, getArtifactDisplay } from "../_utils/formatters";
import { useElapsedTime, type Project, type AgentEvent, type LaneState } from "../_hooks/useProjectState";
import type { ProjectTokenUsage } from "@/lib/api";

interface PhaseColor {
  border: string;
  bg: string;
  bgBright: string;
  text: string;
  glow: string;
  dimBorder: string;
  dimBg: string;
  dimText: string;
}

const PHASE_COLORS: Record<string, PhaseColor> = {
  explore: {
    border: "border-emerald-500", bg: "bg-emerald-500/10", bgBright: "bg-emerald-500/20",
    text: "text-emerald-500", glow: "0 4px 24px -4px rgba(16,185,129,0.35)",
    dimBorder: "border-emerald-500/40", dimBg: "bg-emerald-500/5", dimText: "text-emerald-400",
  },
  hypothesize: {
    border: "border-blue-500", bg: "bg-blue-500/10", bgBright: "bg-blue-500/20",
    text: "text-blue-500", glow: "0 4px 24px -4px rgba(59,130,246,0.35)",
    dimBorder: "border-blue-500/40", dimBg: "bg-blue-500/5", dimText: "text-blue-400",
  },
  evidence: {
    border: "border-cyan-500", bg: "bg-cyan-500/10", bgBright: "bg-cyan-500/20",
    text: "text-cyan-500", glow: "0 4px 24px -4px rgba(6,182,212,0.35)",
    dimBorder: "border-cyan-500/40", dimBg: "bg-cyan-500/5", dimText: "text-cyan-400",
  },
  compose: {
    border: "border-amber-500", bg: "bg-amber-500/10", bgBright: "bg-amber-500/20",
    text: "text-amber-500", glow: "0 4px 24px -4px rgba(245,158,11,0.35)",
    dimBorder: "border-amber-500/40", dimBg: "bg-amber-500/5", dimText: "text-amber-400",
  },
  synthesize: {
    border: "border-violet-500", bg: "bg-violet-500/10", bgBright: "bg-violet-500/20",
    text: "text-violet-500", glow: "0 4px 24px -4px rgba(139,92,246,0.35)",
    dimBorder: "border-violet-500/40", dimBg: "bg-violet-500/5", dimText: "text-violet-400",
  },
  complete: {
    border: "border-green-500", bg: "bg-green-500/10", bgBright: "bg-green-500/20",
    text: "text-green-500", glow: "0 4px 24px -4px rgba(34,197,94,0.35)",
    dimBorder: "border-green-500/40", dimBg: "bg-green-500/5", dimText: "text-green-400",
  },
};

interface OverviewSectionProps {
  project: Project;
  currentAgent: { agent: string; task: string } | null;
  currentIteration: number;
  agentEvents: AgentEvent[];
  laneState: LaneState | null;
  tokenUsage: ProjectTokenUsage | null;
  actionLoading: boolean;
  onToggleRunning: () => void;
  blackboard: {
    artifacts: Record<string, unknown[]>;
    isLoading: boolean;
  };
  wsStatus: string;
}

export function OverviewSection({
  project,
  currentAgent,
  currentIteration,
  agentEvents,
  laneState,
  tokenUsage,
  actionLoading,
  onToggleRunning,
  blackboard,
  wsStatus,
}: OverviewSectionProps) {
  const { t } = useLocale();
  const currentIdx = PHASES.findIndex((p) => p.key === project.phase);
  const isDone = project.status === "completed";
  const [expandedPhase, setExpandedPhase] = useState<string | null>(null);

  return (
    <div className="space-y-6 animate-fade-in">
      <StatusBanner
        project={project}
        currentAgent={currentAgent}
        currentIteration={currentIteration}
        actionLoading={actionLoading}
        onToggleRunning={onToggleRunning}
        wsStatus={wsStatus}
      />

      {/* Research Pipeline — Canvas */}
      <div className="space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-aide-text-muted">
          {t("section.researchPipeline")}
        </h2>

        <Card>
          <CardContent className="p-0">
            {/* Horizontal canvas area */}
            <div className="canvas-grid overflow-x-auto rounded-xl p-8">
              <div className="flex items-center gap-0 min-w-max">
                {PHASES.map((phase, idx) => {
                  const Icon = phase.icon;
                  const isActive = phase.key === project.phase && !isDone;
                  const isComplete = isDone || idx < currentIdx;
                  const isFuture = !isDone && idx > currentIdx;
                  const colors = PHASE_COLORS[phase.key] ?? PHASE_COLORS.explore;
                  const phaseArtifacts = getPhaseArtifactCount(phase.key, blackboard.artifacts);
                  const isExpanded = expandedPhase === phase.key;

                  return (
                    <div key={phase.key} className="flex items-center">
                      {/* Phase Node */}
                      <button
                        onClick={() =>
                          !isFuture && setExpandedPhase(isExpanded ? null : phase.key)
                        }
                        disabled={isFuture}
                        className={`relative flex-shrink-0 rounded-xl border-2 p-4 w-[220px] h-[96px] transition-all duration-200 text-left ${
                          isActive
                            ? `${colors.border} ${isExpanded ? colors.bgBright : colors.bg} ${isExpanded ? "" : "animate-ring-pulse"}`
                            : isComplete
                              ? `${isExpanded ? colors.border : colors.dimBorder} ${isExpanded ? colors.bgBright : colors.dimBg}`
                              : "border-dashed border-aide-border bg-aide-bg-tertiary opacity-50"
                        } ${!isFuture ? "hover:shadow-card-hover cursor-pointer" : ""}`}
                        style={isExpanded ? { boxShadow: colors.glow, transform: "scale(1.03)" } : undefined}
                      >
                        <div className="flex items-center gap-2">
                          <Icon className={`h-4 w-4 ${
                            isActive || isExpanded ? colors.text : isComplete ? colors.dimText : "text-aide-text-muted"
                          }`} />
                          <span className={`text-sm font-semibold ${
                            isActive || isExpanded ? colors.text : isComplete ? colors.dimText : "text-aide-text-muted"
                          }`}>
                            {t(phase.label)}
                          </span>
                          {isComplete && (
                            <CheckCircle2 className={`ml-auto h-3.5 w-3.5 ${isExpanded ? colors.text : colors.dimText}`} />
                          )}
                        </div>
                        <div className="mt-1 flex items-center gap-2 text-xs text-aide-text-muted">
                          {phaseArtifacts > 0 && (
                            <Badge variant={isActive ? "phase" : "default"}>
                              {phaseArtifacts} {t("artifact.items")}
                            </Badge>
                          )}
                          {isActive && currentAgent && (
                            <Badge variant="agent">{currentAgent.agent}</Badge>
                          )}
                          {isActive && currentIteration > 0 && (
                            <span className="text-aide-text-muted">{t("misc.iter")} {currentIteration}</span>
                          )}
                        </div>
                      </button>

                      {/* SVG Arrow Connector */}
                      {idx < PHASES.length - 1 && (
                        <svg width="56" height="20" className="flex-shrink-0">
                          <defs>
                            <marker
                              id={`arrow-${idx}`}
                              markerWidth="8"
                              markerHeight="8"
                              refX="6"
                              refY="4"
                              orient="auto"
                            >
                              <path
                                d="M0,0 L8,4 L0,8 z"
                                fill={isComplete ? "var(--aide-accent-green)" : "var(--aide-border)"}
                              />
                            </marker>
                          </defs>
                          <line
                            x1="4"
                            y1="10"
                            x2="46"
                            y2="10"
                            stroke={isComplete ? "var(--aide-accent-green)" : "var(--aide-border)"}
                            strokeWidth="2"
                            markerEnd={`url(#arrow-${idx})`}
                          />
                        </svg>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Expanded Artifacts Panel */}
            {expandedPhase && (
              <div className="border-t border-aide-border p-5">
                <PhaseArtifacts phase={expandedPhase} artifacts={blackboard.artifacts} />
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Lane Progress */}
      {laneState && laneState.total > 1 && (
        <Card>
          <CardContent>
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="h-4 w-4 text-aide-accent-blue" />
              <span className="text-sm font-medium text-aide-text-primary">
                {laneState.synthesizing
                  ? t("status.synthesizing")
                  : `${t("misc.parallelLanes")} (${laneState.completed.length + laneState.errors.length}/${laneState.total})`}
              </span>
            </div>
            <div className="flex gap-2">
              {Array.from({ length: laneState.total }, (_, i) => {
                const isDone = laneState.completed.includes(i);
                const isError = laneState.errors.includes(i);
                return (
                  <div
                    key={i}
                    className={`flex-1 rounded-lg px-3 py-2 text-center text-xs font-medium ${
                      isDone
                        ? "bg-aide-accent-green/15 text-aide-accent-green"
                        : isError
                          ? "bg-red-500/15 text-red-400"
                          : "bg-aide-accent-blue/10 text-aide-accent-blue"
                    }`}
                  >
                    {t("misc.lane")} {i}
                    {!isDone && !isError && (
                      <Loader2 className="ml-1 inline h-3 w-3 animate-spin" />
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Token Usage & Time Info */}
      <div className="grid grid-cols-2 gap-4">
        <TimeInfoCard project={project} />
        {tokenUsage && <TokenSummaryCard tokenUsage={tokenUsage} />}
      </div>

      {/* Recent Activity */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-aide-text-muted">
          {t("section.recentActivity")}
        </h3>
        {agentEvents.length === 0 ? (
          <p className="text-sm text-aide-text-muted">{t("empty.noActivity")}</p>
        ) : (
          <div className="space-y-2">
            {agentEvents.slice(0, 10).map((evt) => (
              <Card
                key={evt.id}
                className="animate-slide-up"
              >
                <CardContent className="py-2.5">
                  <div className="flex items-center justify-between">
                    <Badge variant="agent">{evt.agent}</Badge>
                    <span className="text-xs text-aide-text-muted">{formatDateTime(evt.timestamp)}</span>
                  </div>
                  <p className="mt-1 text-xs text-aide-text-secondary">{evt.action}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Sub-components ──────────────────────────────────────────── */

function StatusBanner({
  project,
  currentAgent,
  currentIteration,
  actionLoading,
  onToggleRunning,
  wsStatus,
}: {
  project: Project;
  currentAgent: { agent: string; task: string } | null;
  currentIteration: number;
  actionLoading: boolean;
  onToggleRunning: () => void;
  wsStatus: string;
}) {
  const { t } = useLocale();
  const isRunning = project.status === "running";
  const currentPhaseMeta = PHASES.find((p) => p.key === project.phase);

  const bannerClass = isRunning
    ? "border-aide-accent-blue/30 bg-aide-accent-blue/5"
    : project.status === "completed"
      ? "border-aide-accent-green/30 bg-aide-accent-green/5"
      : project.status === "paused"
        ? "border-aide-accent-amber/30 bg-aide-accent-amber/5"
        : "border-aide-border bg-aide-bg-secondary";

  const statusColor = isRunning
    ? "text-aide-accent-blue"
    : project.status === "completed"
      ? "text-aide-accent-green"
      : project.status === "paused"
        ? "text-aide-accent-amber"
        : "text-aide-text-muted";

  const statusLabel = isRunning
    ? t("status.researchRunning")
    : project.status === "completed"
      ? t("status.researchComplete")
      : project.status === "paused"
        ? t("status.researchPaused")
        : project.status;

  return (
    <Card className={bannerClass}>
      <CardContent className="flex items-center gap-3 py-4">
        {isRunning && (
          <span className="relative flex h-2.5 w-2.5 flex-shrink-0">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-aide-accent-blue opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-aide-accent-blue" />
          </span>
        )}
        {project.status === "completed" && <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-aide-accent-green" />}
        {project.status === "paused" && <Pause className="h-4 w-4 flex-shrink-0 text-aide-accent-amber" />}

        <div className="flex flex-1 items-center gap-2 min-w-0">
          <span className={`text-sm font-medium ${statusColor}`}>{statusLabel}</span>
          {currentPhaseMeta && (
            <>
              <span className="text-aide-text-muted">·</span>
              <span className="text-sm text-aide-text-secondary">{t(currentPhaseMeta.label)}</span>
            </>
          )}
          {currentIteration > 0 && (
            <>
              <span className="text-aide-text-muted">·</span>
              <span className="text-sm text-aide-text-muted">{t("misc.iter")} {currentIteration}</span>
            </>
          )}
          {currentAgent && (
            <>
              <span className="text-aide-text-muted">·</span>
              <Badge variant="agent">{currentAgent.agent}</Badge>
            </>
          )}
        </div>

        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="flex items-center gap-1.5">
            <div
              className={`h-2 w-2 rounded-full ${
                wsStatus === "connected"
                  ? "bg-aide-accent-green"
                  : wsStatus === "connecting"
                    ? "bg-aide-accent-amber animate-pulse-subtle"
                    : "bg-aide-text-muted"
              }`}
            />
            <span className="text-xs text-aide-text-muted">
              {wsStatus === "connected" ? t("status.live") : wsStatus === "connecting" ? "..." : t("status.offline")}
            </span>
          </div>

          {project.status !== "completed" && (
            <Button
              variant={isRunning ? "outline" : "primary"}
              size="sm"
              onClick={onToggleRunning}
              disabled={actionLoading}
            >
              {actionLoading ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : isRunning ? (
                <><Pause className="mr-1.5 h-3.5 w-3.5" />{t("action.pause")}</>
              ) : (
                <><Play className="mr-1.5 h-3.5 w-3.5" />{project.status === "paused" ? t("action.resume") : t("action.start")}</>
              )}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function TimeInfoCard({ project }: { project: Project }) {
  const { t } = useLocale();
  const isRunning = project.status === "running";
  const totalElapsed = useElapsedTime(project.created_at, isRunning);

  return (
    <Card>
      <CardContent className="py-4">
        <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-aide-text-muted">{t("section.time")}</h4>
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs text-aide-text-muted">
            <Calendar className="h-3 w-3 flex-shrink-0" />
            <span>{t("time.created")} {formatDateTimeFull(project.created_at)}</span>
          </div>
          {isRunning && totalElapsed && (
            <div className="flex items-center gap-2 text-xs text-aide-accent-blue">
              <Clock className="h-3 w-3 flex-shrink-0 animate-pulse-subtle" />
              <span>{t("time.runningFor")} {totalElapsed}</span>
            </div>
          )}
          {project.status === "completed" && (
            <div className="flex items-center gap-2 text-xs text-aide-accent-green">
              <CheckCircle2 className="h-3 w-3 flex-shrink-0" />
              <span>{t("time.completedAt")} {formatDateTimeFull(project.updated_at)}</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function TokenSummaryCard({ tokenUsage }: { tokenUsage: ProjectTokenUsage }) {
  const { t } = useLocale();
  return (
    <Card>
      <CardContent className="py-4">
        <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-aide-text-muted">{t("section.tokenUsage")}</h4>
        <div className="grid grid-cols-3 gap-2 text-xs">
          <div>
            <p className="text-aide-text-muted">{t("misc.tokens")}</p>
            <p className="mt-0.5 text-sm font-semibold text-aide-text-primary">
              {tokenUsage.total_tokens.toLocaleString()}
            </p>
          </div>
          <div>
            <p className="text-aide-text-muted">USD</p>
            <p className="mt-0.5 text-sm font-semibold text-aide-accent-blue">
              ${tokenUsage.total_cost_usd.toFixed(4)}
            </p>
          </div>
          <div>
            <p className="text-aide-text-muted">RMB</p>
            <p className="mt-0.5 text-sm font-semibold text-aide-accent-green">
              ¥{tokenUsage.total_cost_rmb.toFixed(4)}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

const ARTIFACT_TYPE_STYLES: Record<string, { labelKey: I18nKey; dot: string; border: string }> = {
  directions:        { labelKey: "artifact.directions",        dot: "bg-emerald-400", border: "border-l-emerald-500" },
  trend_signals:     { labelKey: "artifact.trend_signals",     dot: "bg-cyan-400",    border: "border-l-cyan-500" },
  hypotheses:        { labelKey: "artifact.hypotheses",        dot: "bg-blue-400",    border: "border-l-blue-500" },
  evidence_findings: { labelKey: "artifact.evidence_findings", dot: "bg-amber-400",   border: "border-l-amber-500" },
  evidence_gaps:     { labelKey: "artifact.evidence_gaps",     dot: "bg-orange-400",  border: "border-l-orange-500" },
  experiment_guide:  { labelKey: "artifact.experiment_guide",  dot: "bg-teal-400",    border: "border-l-teal-500" },
  outline:           { labelKey: "artifact.outline",           dot: "bg-violet-400",  border: "border-l-violet-500" },
  draft:             { labelKey: "artifact.draft",             dot: "bg-indigo-400",  border: "border-l-indigo-500" },
  review:            { labelKey: "artifact.review",            dot: "bg-rose-400",    border: "border-l-rose-500" },
};

function ExpandableArtifactCard({
  artifact,
  index,
}: {
  artifact: { id?: string; data?: Record<string, unknown> };
  index: number;
}) {
  const { t } = useLocale();
  const [expanded, setExpanded] = useState(false);
  const { main, sub } = getArtifactDisplay(artifact.data ?? {});
  const canExpand = main.length > 100 || (sub ? sub.length > 60 : false);

  const rawType = (artifact.data?.artifact_type as string) ?? "";
  const typeStyle = ARTIFACT_TYPE_STYLES[rawType];

  return (
    <div
      className={`animate-slide-up stagger-${Math.min(index + 1, 5)} group rounded-xl border border-aide-border/60 border-l-[3px] ${typeStyle?.border ?? "border-l-aide-border"} bg-aide-bg-secondary transition-all duration-200 hover:border-aide-border hover:shadow-md ${canExpand ? "cursor-pointer" : ""} ${expanded ? "bg-aide-bg-tertiary shadow-md" : ""}`}
      style={{ opacity: 0, animationFillMode: "forwards" }}
      onClick={() => canExpand && setExpanded(!expanded)}
    >
      <div className="px-4 py-3.5">
        {/* Type badge + collapse control */}
        <div className="mb-2 flex items-center justify-between">
          {typeStyle ? (
            <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-aide-text-muted">
              <span className={`h-1.5 w-1.5 rounded-full ${typeStyle.dot}`} />
              {t(typeStyle.labelKey)}
            </span>
          ) : (
            <span />
          )}
          {expanded && canExpand && (
            <span className="text-[10px] font-semibold uppercase tracking-wider text-aide-accent-blue hover:underline">
              {t("action.collapseUp")}
            </span>
          )}
        </div>

        {/* Main title */}
        <Markdown className={`md-content text-[13px] font-medium leading-snug text-aide-text-primary ${!expanded && canExpand ? "line-clamp-3" : ""}`}>
          {main}
        </Markdown>

        {/* Sub content */}
        {sub && (
          <div className={`mt-2.5 rounded-lg ${expanded ? "bg-aide-bg-primary/50 px-3 py-2.5" : ""}`}>
            <Markdown className={`md-content text-xs leading-relaxed text-aide-text-secondary ${!expanded && canExpand ? "line-clamp-3" : ""}`}>
              {sub}
            </Markdown>
          </div>
        )}

        {/* Expand prompt */}
        {!expanded && canExpand && (
          <div className="mt-2.5 flex items-center gap-1 text-[11px] font-medium text-aide-accent-blue opacity-70 transition-opacity group-hover:opacity-100">
            <span>{t("action.expandAll")}</span>
            <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        )}
      </div>
    </div>
  );
}

function PhaseArtifacts({ phase, artifacts }: { phase: string; artifacts: Record<string, unknown[]> }) {
  const { t } = useLocale();
  const [showAll, setShowAll] = useState(false);
  const mapping: Record<string, string[]> = {
    explore: ["directions", "trend_signals"],
    hypothesize: ["hypotheses"],
    evidence: ["evidence_findings", "evidence_gaps", "experiment_guide"],
    compose: ["outline", "draft"],
    synthesize: ["draft", "outline"],
    complete: ["review"],
  };

  const types = mapping[phase] ?? [];
  const items: unknown[] = [];
  for (const tp of types) {
    const arr = artifacts[tp];
    if (Array.isArray(arr)) items.push(...arr);
  }

  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-aide-border p-4 text-center text-xs text-aide-text-muted">
        {t("empty.noArtifactsPhase")}
      </div>
    );
  }

  const INITIAL_COUNT = 6;
  const visible = showAll ? items : items.slice(0, INITIAL_COUNT);

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        {visible.map((item, i) => {
          const artifact = item as { id?: string; data?: Record<string, unknown> };
          return (
            <ExpandableArtifactCard key={artifact.id ?? i} artifact={artifact} index={i} />
          );
        })}
      </div>
      {items.length > INITIAL_COUNT && (
        <button
          onClick={() => setShowAll(!showAll)}
          className="mx-auto flex items-center gap-1.5 rounded-lg border border-aide-border/60 bg-aide-bg-tertiary px-4 py-1.5 text-xs font-medium text-aide-text-secondary transition-colors hover:border-aide-accent-blue/40 hover:text-aide-accent-blue"
        >
          {showAll ? t("action.showFirstN", { n: INITIAL_COUNT }) : t("action.showAllN", { n: items.length })}
        </button>
      )}
    </div>
  );
}

function getPhaseArtifactCount(phase: string, artifacts: Record<string, unknown[]>): number {
  const mapping: Record<string, string[]> = {
    explore: ["directions", "trend_signals"],
    hypothesize: ["hypotheses"],
    evidence: ["evidence_findings", "evidence_gaps", "experiment_guide"],
    compose: ["outline", "draft"],
    synthesize: ["draft", "outline"],
    complete: ["review"],
  };
  const types = mapping[phase] ?? [];
  let count = 0;
  for (const tp of types) {
    const arr = artifacts[tp];
    if (Array.isArray(arr)) count += arr.length;
  }
  return count;
}
