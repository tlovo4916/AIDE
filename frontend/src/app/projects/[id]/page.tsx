"use client";

import { useEffect, useState, useCallback } from "react";
import { Markdown } from "@/components/ui/markdown";
import { useParams, useRouter } from "next/navigation";
import {
  Play,
  Pause,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  FileText,
  Lightbulb,
  Search,
  BookOpen,
  PenTool,
  CheckCircle2,
  Loader2,
  ArrowLeft,
  X,
  Trash2,
  Clock,
  Calendar,
  TrendingUp,
  Download,
} from "lucide-react";
import Link from "next/link";
import {
  getProject,
  respondToCheckpoint,
  startProject,
  pauseProject,
  resumeProject,
  deleteProject,
  getExportedPaper,
  getProjectUsage,
  getPaperHtml,
  savePaperContent,
  getCitationGraph,
  type ProjectTokenUsage,
  type CitationGraphData,
} from "@/lib/api";
import { PapersPanel } from "@/components/papers-panel";
import { useTypedWebSocket } from "@/hooks/useTypedWebSocket";
import { useBlackboard } from "@/hooks/useBlackboard";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";

interface Project {
  id: string;
  name: string;
  research_topic: string;
  concurrency?: number;
  phase: string;
  status: string;
  created_at: string;
  updated_at: string;
}

interface AgentEvent {
  id: string;
  agent: string;
  action: string;
  timestamp: string;
}

interface Checkpoint {
  id: string;
  phase: string;
  summary: string;
  options: { label: string; value: string }[];
}

const PHASES = [
  { key: "explore", label: "Explore", icon: Search },
  { key: "hypothesize", label: "Hypothesize", icon: Lightbulb },
  { key: "evidence", label: "Evidence", icon: FileText },
  { key: "compose", label: "Compose", icon: BookOpen },
  { key: "synthesize", label: "Synthesize", icon: TrendingUp },
  { key: "complete", label: "Complete", icon: CheckCircle2 },
];

const ARTIFACT_SECTIONS = [
  { type: "directions", label: "Research Directions", icon: Search },
  { type: "hypotheses", label: "Hypotheses", icon: Lightbulb },
  { type: "evidence_findings", label: "Evidence", icon: FileText },
  { type: "outline", label: "Outline", icon: BookOpen },
  { type: "draft", label: "Draft", icon: PenTool },
  { type: "review", label: "Review", icon: CheckCircle2 },
  { type: "trend_signals", label: "Trend Signals", icon: TrendingUp },
] as const;

type ArtifactType = (typeof ARTIFACT_SECTIONS)[number]["type"];

function getArtifactDisplay(data: Record<string, unknown>): { main: string; sub?: string } {
  // REST endpoint stores content as JSON string in data.content
  let d = data;
  if (typeof data.content === "string" && data.content.trim().startsWith("{")) {
    try { d = JSON.parse(data.content) as Record<string, unknown>; } catch { /* use d as-is */ }
  }

  // Librarian: {findings: [...], sources: [...]}
  if (Array.isArray(d.findings) && (d.findings as unknown[]).length > 0) {
    const lines = (d.findings as unknown[]).map(f => typeof f === "string" ? f : JSON.stringify(f));
    return { main: lines.join("\n") };
  }
  // Director: {title, body}
  if (typeof d.title === "string" && d.title) {
    return { main: d.title, sub: typeof d.body === "string" ? d.body : undefined };
  }
  // Scientist: {hypothesis, methodology}
  if (typeof d.hypothesis === "string" && d.hypothesis) {
    return { main: d.hypothesis, sub: typeof d.methodology === "string" ? d.methodology : undefined };
  }
  // Critic: {score, strengths, weaknesses}
  if (typeof d.score !== "undefined") {
    const weaknesses = Array.isArray(d.weaknesses) ? (d.weaknesses as unknown[]).join("\n") : "";
    const strengths = Array.isArray(d.strengths) ? (d.strengths as unknown[]).join("\n") : "";
    const sub = [strengths && `Strengths:\n${strengths}`, weaknesses && `Weaknesses:\n${weaknesses}`].filter(Boolean).join("\n\n");
    return { main: `Score: ${d.score}/10`, sub: sub || undefined };
  }
  // Writer: {section, text}
  if (typeof d.text === "string" && d.text) {
    return { main: d.text };
  }
  if (typeof d.section === "string" && d.section) {
    return { main: d.section };
  }
  // Fallback: any non-empty string field
  const skip = new Set(["artifact_id", "artifact_type", "created_by", "version", "tags", "superseded", "content", "created_at", "updated_at", "active_count"]);
  for (const [k, v] of Object.entries(d)) {
    if (skip.has(k)) continue;
    if (typeof v === "string" && v) return { main: `${k}: ${v}` };
    if (Array.isArray(v) && (v as unknown[]).length > 0) {
      return { main: `${k}:\n${(v as unknown[]).join("\n")}` };
    }
  }
  // No content fields found — show readable placeholder
  const artType = typeof data.artifact_type === "string"
    ? data.artifact_type.replace(/_/g, " ")
    : "";
  const ver = typeof data.version === "number" ? ` v${data.version}` : "";
  return { main: artType ? `(${artType}${ver} — no content stored)` : "(no content)" };
}

function PhaseProgress({
  currentPhase,
}: {
  currentPhase: string;
}) {
  const currentIdx = PHASES.findIndex((p) => p.key === currentPhase);

  return (
    <div className="space-y-1">
      {PHASES.map((phase, idx) => {
        const Icon = phase.icon;
        const isActive = phase.key === currentPhase;
        const isComplete = idx < currentIdx;

        return (
          <div
            key={phase.key}
            className={`flex items-center gap-2.5 rounded-md px-3 py-2 text-sm ${
              isActive
                ? "bg-aide-accent-blue/10 font-medium text-aide-accent-blue"
                : isComplete
                  ? "text-aide-accent-green"
                  : "text-aide-text-muted"
            }`}
          >
            <Icon className="h-4 w-4 flex-shrink-0" />
            <span>{phase.label}</span>
            {isComplete && (
              <CheckCircle2 className="ml-auto h-3.5 w-3.5" />
            )}
            {isActive && (
              <ChevronRight className="ml-auto h-3.5 w-3.5 animate-pulse-subtle" />
            )}
          </div>
        );
      })}
    </div>
  );
}

function ActivityFeed({ events }: { events: AgentEvent[] }) {
  return (
    <div className="space-y-2">
      <h3 className="px-1 text-xs font-semibold uppercase tracking-wider text-aide-text-muted">
        Agent Activity
      </h3>
      {events.length === 0 ? (
        <p className="px-1 text-xs text-aide-text-muted">
          No activity yet
        </p>
      ) : (
        <div className="space-y-1.5">
          {events.slice(0, 20).map((evt) => (
            <div
              key={evt.id}
              className="rounded-md bg-aide-bg-tertiary px-3 py-2 text-xs animate-slide-up"
            >
              <div className="flex items-center justify-between">
                <Badge variant="agent">{evt.agent}</Badge>
                <span className="text-aide-text-muted">
                  {formatDateTime(evt.timestamp)}
                </span>
              </div>
              <p className="mt-1 text-aide-text-secondary">{evt.action}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const COLLAPSE_THRESHOLD = 300; // chars; cards shorter than this are never collapsible

/** Parse a UTC ISO timestamp from backend (may lack trailing Z). */
function parseTS(ts: string): Date {
  if (ts && !ts.endsWith("Z") && !/[+-]\d{2}:\d{2}$/.test(ts)) {
    return new Date(ts + "Z");
  }
  return new Date(ts);
}

function formatElapsed(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  if (totalSec < 60) return `${totalSec}秒`;
  const totalMin = Math.floor(totalSec / 60);
  if (totalMin < 60) return `${totalMin}分钟`;
  const hours = Math.floor(totalMin / 60);
  const mins = totalMin % 60;
  if (hours < 24) return mins > 0 ? `${hours}小时${mins}分钟` : `${hours}小时`;
  const days = Math.floor(hours / 24);
  const remHours = hours % 24;
  return remHours > 0 ? `${days}天${remHours}小时` : `${days}天`;
}

function formatDateTime(ts: string): string {
  const d = parseTS(ts);
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const h = String(d.getHours()).padStart(2, "0");
  const m = String(d.getMinutes()).padStart(2, "0");
  return `${month}-${day} ${h}:${m}`;
}

function formatDateTimeFull(ts: string): string {
  const d = parseTS(ts);
  const y = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const h = String(d.getHours()).padStart(2, "0");
  const m = String(d.getMinutes()).padStart(2, "0");
  const s = String(d.getSeconds()).padStart(2, "0");
  return `${y}-${month}-${day} ${h}:${m}:${s}`;
}

function useElapsedTime(since: string | undefined, active: boolean) {
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

function ProjectTimeInfo({ project }: { project: Project }) {
  const isRunning = project.status === "running";
  const isPaused = project.status === "paused";
  const isCompleted = project.status === "completed";
  const totalElapsed = useElapsedTime(project.created_at, isRunning);
  const sinceUpdate = useElapsedTime(project.updated_at, isPaused);

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2 text-xs text-aide-text-muted">
        <Calendar className="h-3 w-3 flex-shrink-0" />
        <span>创建于 {formatDateTimeFull(project.created_at)}</span>
      </div>
      {isRunning && (
        <div className="flex items-center gap-2 text-xs text-aide-accent-blue">
          <Clock className="h-3 w-3 flex-shrink-0 animate-pulse-subtle" />
          <span>已运行 {totalElapsed}</span>
        </div>
      )}
      {isPaused && (
        <div className="flex items-center gap-2 text-xs text-aide-accent-amber">
          <Pause className="h-3 w-3 flex-shrink-0" />
          <span>已暂停 {sinceUpdate}（{formatDateTime(project.updated_at)}起）</span>
        </div>
      )}
      {isCompleted && (
        <div className="flex items-center gap-2 text-xs text-aide-accent-green">
          <CheckCircle2 className="h-3 w-3 flex-shrink-0" />
          <span>完成于 {formatDateTimeFull(project.updated_at)}</span>
        </div>
      )}
      {!isRunning && !isPaused && !isCompleted && (
        <div className="flex items-center gap-2 text-xs text-aide-text-muted">
          <Clock className="h-3 w-3 flex-shrink-0" />
          <span>上次更新 {formatDateTime(project.updated_at)}</span>
        </div>
      )}
    </div>
  );
}

function ArtifactCard({ item }: { item: unknown }) {
  const artifact = item as { id: string; type: string; data: Record<string, unknown> };
  const { main, sub } = getArtifactDisplay(artifact.data ?? {});
  const author = typeof artifact.data?.created_by === "string" ? artifact.data.created_by : undefined;

  const totalLen = main.length + (sub?.length ?? 0);
  const collapsible = totalLen > COLLAPSE_THRESHOLD;
  const [expanded, setExpanded] = useState(false);

  return (
    <Card variant="default" className="animate-slide-up">
      <CardContent className="py-3">
        {author && (
          <div className="mb-1.5">
            <Badge variant="agent">{author}</Badge>
          </div>
        )}
        <Markdown className={`md-content${collapsible && !expanded ? " line-clamp-4" : ""}`}>
          {main}
        </Markdown>
        {sub && (
          <Markdown className={`md-content md-sub mt-2${collapsible && !expanded ? " line-clamp-2" : ""}`}>
            {sub}
          </Markdown>
        )}
        {collapsible && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="mt-2 flex items-center gap-1 text-xs text-aide-accent-blue hover:opacity-70 transition-opacity"
          >
            {expanded ? (
              <><ChevronUp className="h-3 w-3" />Collapse</>
            ) : (
              <><ChevronDown className="h-3 w-3" />Show more</>
            )}
          </button>
        )}
      </CardContent>
    </Card>
  );
}

function ArtifactSection({
  type,
  label,
  icon: Icon,
  artifacts,
}: {
  type: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  artifacts: Record<string, unknown[]>;
}) {
  const items = artifacts[type] ?? [];

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 text-aide-text-muted" />
        <h3 className="text-sm font-medium text-aide-text-secondary">
          {label}
        </h3>
        {items.length > 0 && (
          <span className="ml-auto text-xs text-aide-text-muted">
            {items.length}
          </span>
        )}
      </div>
      {items.length === 0 ? (
        <div className="rounded-md border border-dashed border-aide-border px-4 py-6 text-center text-xs text-aide-text-muted">
          No {label.toLowerCase()} yet
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item: unknown, i: number) => (
            <ArtifactCard key={i} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}

function ChallengePanel({
  challenges,
}: {
  challenges: { id: string; from: string; message: string; resolved: boolean }[];
}) {
  const active = challenges.filter((c) => !c.resolved);
  const resolved = challenges.filter((c) => c.resolved);

  return (
    <div className="space-y-3">
      <h3 className="px-1 text-xs font-semibold uppercase tracking-wider text-aide-text-muted">
        Challenges
      </h3>
      {active.length === 0 && resolved.length === 0 && (
        <p className="px-1 text-xs text-aide-text-muted">
          No challenges raised
        </p>
      )}
      {active.map((c) => (
        <Card key={c.id} variant="challenge" className="animate-slide-up">
          <CardContent className="py-3">
            <div className="mb-1 flex items-center gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5 text-aide-accent-amber" />
              <Badge variant="agent">{c.from}</Badge>
            </div>
            <p className="text-xs text-aide-text-primary">{c.message}</p>
          </CardContent>
        </Card>
      ))}
      {resolved.map((c) => (
        <Card key={c.id} variant="default" className="opacity-60">
          <CardContent className="py-3">
            <div className="mb-1 flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-aide-accent-green" />
              <Badge variant="agent">{c.from}</Badge>
            </div>
            <p className="text-xs text-aide-text-secondary line-through">
              {c.message}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function MessageStream({
  messages,
}: {
  messages: { id: string; role: string; content: string; timestamp: string }[];
}) {
  return (
    <div className="space-y-3">
      <h3 className="px-1 text-xs font-semibold uppercase tracking-wider text-aide-text-muted">
        Message Stream
      </h3>
      {messages.length === 0 ? (
        <p className="px-1 text-xs text-aide-text-muted">
          Waiting for messages...
        </p>
      ) : (
        <div className="space-y-2">
          {messages.slice(-30).map((msg) => (
            <div
              key={msg.id}
              className="rounded-md bg-aide-bg-tertiary px-3 py-2 animate-slide-up"
            >
              <div className="mb-1 flex items-center justify-between">
                <span className="text-xs font-medium text-aide-accent-blue">
                  {msg.role}
                </span>
                <span className="text-xs text-aide-text-muted">
                  {formatDateTime(msg.timestamp)}
                </span>
              </div>
              <p className="text-xs text-aide-text-secondary">{msg.content}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ProjectPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const router = useRouter();

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
  const [showPaperModal, setShowPaperModal] = useState(false);
  const [paperEditing, setPaperEditing] = useState(false);
  const [paperEditContent, setPaperEditContent] = useState("");
  const [paperSaving, setPaperSaving] = useState(false);
  const [tokenUsage, setTokenUsage] = useState<ProjectTokenUsage | null>(null);
  const [citationGraph, setCitationGraph] = useState<CitationGraphData | null>(null);
  const [showCitationGraph, setShowCitationGraph] = useState(false);
  const [laneState, setLaneState] = useState<{
    total: number;
    completed: number[];
    errors: number[];
    synthesizing: boolean;
  } | null>(null);

  const ws = useTypedWebSocket(projectId);
  const blackboard = useBlackboard(ws, projectId);

  useEffect(() => {
    getProject(projectId)
      .then((p) => {
        setProject(p);
        if (p.status === "completed") {
          getProjectUsage(projectId).then(setTokenUsage).catch(() => {});
        }
      })
      .catch(() => setProject(null))
      .finally(() => setLoading(false));
  }, [projectId]);

  useEffect(() => {
    const timer = setInterval(() => {
      getProject(projectId)
        .then((p) => setProject((prev) => prev ? { ...prev, phase: p.phase, status: p.status, updated_at: p.updated_at } : p))
        .catch(() => {});
    }, 30_000);
    return () => clearInterval(timer);
  }, [projectId]);

  useEffect(() => {
    if (!ws.subscribe) return;

    const unsubs = [
      ws.subscribe("AgentStarted", (payload) => {
        setCurrentAgent({ agent: payload.agent, task: payload.task });
        setCurrentIteration(payload.iteration);
        // 同步 phase
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
      ws.subscribe("AgentError", () => {
        setCurrentAgent(null);
      }),
      ws.subscribe("CheckpointCreated", (payload) => {
        setCurrentAgent(null);
        setCheckpoint(payload as unknown as Checkpoint);
      }),
      ws.subscribe("CheckpointResolved", () => {
        setCheckpoint(null);
      }),
      ws.subscribe("PhaseAdvanced", (payload) => {
        setProject((prev) =>
          prev ? { ...prev, phase: payload.phase } : prev
        );
      }),
      ws.subscribe("TopicDriftWarning", (payload) => {
        setTopicDriftWarning(payload.message);
        // 5 秒后自动隐藏
        setTimeout(() => setTopicDriftWarning(null), 8_000);
      }),
      ws.subscribe("LanesStarted", (payload) => {
        setLaneState({
          total: payload.num_lanes,
          completed: [],
          errors: [],
          synthesizing: false,
        });
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
        // Capture token usage from WS event
        if (payload.token_usage) {
          setTokenUsage(payload.token_usage as unknown as ProjectTokenUsage);
        } else {
          // Fallback: fetch from API
          getProjectUsage(projectId).then(setTokenUsage).catch(() => {});
        }
        // Auto-load paper content
        getExportedPaper(projectId)
          .then((data) => {
            setPaperContent(data.content);
            setShowPaperModal(true);
          })
          .catch(() => {});
      }),
    ];

    return () => unsubs.forEach((fn) => fn());
  }, [ws]);

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
      router.push("/");
    } finally {
      setDeleting(false);
    }
  }, [projectId, router]);

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

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-6 w-6 animate-spin text-aide-accent-blue" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <p className="mb-4 text-aide-text-secondary">Project not found</p>
        <Link href="/">
          <Button variant="secondary" size="md">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Dashboard
          </Button>
        </Link>
      </div>
    );
  }

  const isRunning = project.status === "running";
  const currentPhaseMeta = PHASES.find((p) => p.key === project.phase);

  return (
    <div className="animate-fade-in">
      {/* 偏题警告 Toast */}
      {topicDriftWarning && (
        <div className="fixed bottom-6 right-6 z-50 flex max-w-sm items-start gap-3 rounded-lg border border-aide-accent-amber/50 bg-aide-bg-secondary px-4 py-3 shadow-xl animate-slide-up">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-aide-accent-amber" />
          <div>
            <p className="text-xs font-semibold text-aide-accent-amber">研究偏题警告</p>
            <p className="mt-0.5 text-xs text-aide-text-secondary">{topicDriftWarning}</p>
          </div>
          <button onClick={() => setTopicDriftWarning(null)} className="ml-auto text-aide-text-muted hover:text-aide-text-primary">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Top Bar */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="rounded-md p-1.5 text-aide-text-muted transition-colors hover:bg-aide-bg-tertiary hover:text-aide-text-primary"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-xl font-semibold text-aide-text-primary">
              {project.name}
            </h1>
            <p className="text-sm text-aide-text-secondary">
              {project.research_topic}
            </p>
            <div className="mt-1">
              <ProjectTimeInfo project={project} />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="phase">
            {PHASES.find((p) => p.key === project.phase)?.label ??
              project.phase}
          </Badge>
          <Badge variant={isRunning ? "success" : "warning"}>
            {project.status}
          </Badge>
          <div className="flex items-center gap-1.5">
            <div
              className={`h-2 w-2 rounded-full ${
                ws.status === "connected"
                  ? "bg-aide-accent-green"
                  : ws.status === "connecting"
                    ? "bg-aide-accent-amber animate-pulse-subtle"
                    : "bg-aide-text-muted"
              }`}
            />
            <span className="text-xs text-aide-text-muted">
              {ws.status === "connected"
                ? "Live"
                : ws.status === "connecting"
                  ? "Connecting"
                  : "Offline"}
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowDeleteConfirm(true)}
            className="text-aide-text-muted hover:bg-red-500/10 hover:text-red-400"
            title="删除项目"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={async () => {
              try {
                const data = await getCitationGraph(projectId);
                if (data.total_papers > 0) {
                  setCitationGraph(data);
                  setShowCitationGraph(true);
                }
              } catch { /* no graph yet */ }
            }}
            title="引用图谱"
          >
            <TrendingUp className="mr-1.5 h-3.5 w-3.5" />
            引用图谱
          </Button>
          {project.status === "completed" && (
            <Button
              variant="secondary"
              size="sm"
              onClick={async () => {
                try {
                  const [data, usage] = await Promise.all([
                    getExportedPaper(projectId),
                    getProjectUsage(projectId).catch(() => null),
                  ]);
                  setPaperContent(data.content);
                  if (usage) setTokenUsage(usage);
                  setShowPaperModal(true);
                } catch {
                  /* paper not available */
                }
              }}
            >
              <BookOpen className="mr-1.5 h-3.5 w-3.5" />
              查看论文
            </Button>
          )}
          <Button
            variant={isRunning ? "secondary" : "primary"}
            size="sm"
            onClick={handleToggleRunning}
            disabled={actionLoading}
          >
            {actionLoading ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : isRunning ? (
              <>
                <Pause className="mr-1.5 h-3.5 w-3.5" />
                Pause
              </>
            ) : (
              <>
                <Play className="mr-1.5 h-3.5 w-3.5" />
                {project.status === "paused" ? "Resume" : "Start"}
              </>
            )}
          </Button>
        </div>
      </div>

      {/* 研究运行中横幅 */}
      {isRunning && (
        <div className="mb-4 flex items-center gap-3 rounded-lg border border-aide-accent-blue/30 bg-aide-accent-blue/5 px-4 py-3">
          <span className="relative flex h-2.5 w-2.5 flex-shrink-0">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-aide-accent-blue opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-aide-accent-blue" />
          </span>
          <div className="flex flex-1 items-center gap-2 min-w-0">
            <span className="text-sm font-medium text-aide-accent-blue">研究进行中</span>
            {currentPhaseMeta && (
              <>
                <span className="text-aide-text-muted">·</span>
                <span className="text-sm text-aide-text-secondary">{currentPhaseMeta.label} 阶段</span>
              </>
            )}
            {currentIteration > 0 && (
              <>
                <span className="text-aide-text-muted">·</span>
                <span className="text-sm text-aide-text-muted">第 {currentIteration} 轮</span>
              </>
            )}
            {currentAgent && (
              <>
                <span className="text-aide-text-muted">·</span>
                <Badge variant="agent">{currentAgent.agent}</Badge>
                <span className="text-xs text-aide-text-muted truncate">{currentAgent.task.slice(0, 60)}{currentAgent.task.length > 60 ? "…" : ""}</span>
              </>
            )}
          </div>
          <Loader2 className="h-4 w-4 flex-shrink-0 animate-spin text-aide-accent-blue" />
        </div>
      )}

      {/* 并行 Lane 进度 */}
      {laneState && laneState.total > 1 && (
        <div className="mb-4 rounded-lg border border-aide-border bg-aide-bg-secondary px-4 py-3">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="h-4 w-4 text-aide-accent-blue" />
            <span className="text-sm font-medium text-aide-text-primary">
              {laneState.synthesizing
                ? "综合分析中..."
                : `并行研究 Lane (${laneState.completed.length + laneState.errors.length}/${laneState.total})`}
            </span>
          </div>
          <div className="flex gap-2">
            {Array.from({ length: laneState.total }, (_, i) => {
              const isDone = laneState.completed.includes(i);
              const isError = laneState.errors.includes(i);
              return (
                <div
                  key={i}
                  className={`flex-1 rounded-md px-3 py-2 text-center text-xs ${
                    isDone
                      ? "bg-aide-accent-green/15 text-aide-accent-green"
                      : isError
                        ? "bg-red-500/15 text-red-400"
                        : "bg-aide-accent-blue/10 text-aide-accent-blue"
                  }`}
                >
                  <span className="font-medium">Lane {i}</span>
                  <span className="ml-1.5">
                    {isDone ? "done" : isError ? "error" : "running"}
                  </span>
                  {!isDone && !isError && (
                    <Loader2 className="ml-1 inline h-3 w-3 animate-spin" />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 研究完成横幅 */}
      {project.status === "completed" && (
        <div className="mb-4 flex items-center gap-3 rounded-lg border border-aide-accent-green/30 bg-aide-accent-green/5 px-4 py-3">
          <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-aide-accent-green" />
          <div className="flex flex-1 items-center gap-2 min-w-0">
            <span className="text-sm font-medium text-aide-accent-green">研究已完成</span>
            {tokenUsage && (
              <>
                <span className="text-aide-text-muted">·</span>
                <span className="text-sm text-aide-text-secondary">
                  {tokenUsage.total_tokens.toLocaleString()} tokens
                </span>
                <span className="text-aide-text-muted">·</span>
                <span className="text-sm text-aide-accent-blue">${tokenUsage.total_cost_usd.toFixed(4)}</span>
                <span className="text-aide-text-muted">/</span>
                <span className="text-sm text-aide-accent-green">¥{tokenUsage.total_cost_rmb.toFixed(4)}</span>
              </>
            )}
          </div>
        </div>
      )}

      {/* 研究暂停横幅 */}
      {project.status === "paused" && (
        <div className="mb-4 flex items-center gap-3 rounded-lg border border-aide-accent-amber/30 bg-aide-accent-amber/5 px-4 py-3">
          <Pause className="h-4 w-4 flex-shrink-0 text-aide-accent-amber" />
          <div className="flex flex-1 items-center gap-2 min-w-0">
            <span className="text-sm font-medium text-aide-accent-amber">研究已暂停</span>
            {currentPhaseMeta && (
              <>
                <span className="text-aide-text-muted">·</span>
                <span className="text-sm text-aide-text-secondary">停在 {currentPhaseMeta.label} 阶段</span>
              </>
            )}
            <span className="text-aide-text-muted">·</span>
            <span className="text-sm text-aide-text-muted">
              暂停于 {formatDateTime(project.updated_at)}
            </span>
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={handleToggleRunning}
            disabled={actionLoading}
          >
            {actionLoading ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="mr-1.5 h-3.5 w-3.5" />
            )}
            继续研究
          </Button>
        </div>
      )}

      {/* Three Column Layout */}
      <div className="grid grid-cols-[220px_1fr_260px] gap-4">
        {/* Left Column: Phase Progress + Activity */}
        <div className="space-y-6">
          <div>
            <h3 className="mb-3 px-1 text-xs font-semibold uppercase tracking-wider text-aide-text-muted">
              Phase Progress
            </h3>
            <PhaseProgress currentPhase={project.phase} />
            {currentIteration > 0 && (
              <p className="mt-2 px-1 text-xs text-aide-text-muted">
                迭代次数：{currentIteration}
              </p>
            )}
          </div>
          {/* 当前 Agent 执行状态 */}
          {currentAgent ? (
            <div className="rounded-md border border-aide-accent-blue/30 bg-aide-accent-blue/5 px-3 py-2 text-xs">
              <div className="flex items-center gap-2">
                <Loader2 className="h-3 w-3 animate-spin text-aide-accent-blue" />
                <Badge variant="agent">{currentAgent.agent}</Badge>
                <span className="text-aide-text-muted text-xs">执行中…</span>
              </div>
              <p className="mt-1 text-aide-text-secondary line-clamp-3">{currentAgent.task}</p>
            </div>
          ) : isRunning ? (
            <div className="rounded-md border border-dashed border-aide-border px-3 py-2 text-xs text-aide-text-muted flex items-center gap-2">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-aide-text-muted opacity-60" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-aide-text-muted" />
              </span>
              等待下一个 Agent…
            </div>
          ) : null}
          <ActivityFeed events={agentEvents} />
        </div>

        {/* Center Column: Blackboard */}
        <div className="space-y-6">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-aide-text-muted">
            Blackboard
          </h2>
          {blackboard.isLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-5 w-5 animate-spin text-aide-accent-blue" />
            </div>
          ) : (
            <div className="grid gap-6 md:grid-cols-2">
              {ARTIFACT_SECTIONS.map((section) => (
                <ArtifactSection
                  key={section.type}
                  type={section.type}
                  label={section.label}
                  icon={section.icon}
                  artifacts={
                    blackboard.artifacts as Record<string, unknown[]>
                  }
                />
              ))}
            </div>
          )}
        </div>

        {/* Right Column: Papers + Challenges + Messages */}
        <div className="space-y-6 overflow-y-auto" style={{ maxHeight: "calc(100vh - 120px)" }}>
          <PapersPanel projectId={projectId} />
          <ChallengePanel challenges={blackboard.challenges} />
          <MessageStream messages={blackboard.messages} />
        </div>
      </div>

      {/* Delete Confirm Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-sm rounded-lg border border-aide-border bg-aide-surface p-6 shadow-xl">
            <div className="mb-4 flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-aide-accent-amber" />
              <div>
                <h2 className="text-base font-semibold text-aide-text-primary">删除项目</h2>
                <p className="mt-1 text-sm text-aide-text-secondary">
                  确认删除 <span className="font-medium text-aide-text-primary">{project.name}</span>？
                </p>
                <p className="mt-1 text-xs text-aide-text-muted">
                  此操作不可撤销，将同时删除所有研究 artifacts 和文件数据。
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="md" onClick={() => setShowDeleteConfirm(false)} disabled={deleting}>
                取消
              </Button>
              <Button
                variant="primary"
                size="md"
                onClick={handleDelete}
                disabled={deleting}
                className="bg-red-600 hover:bg-red-700"
              >
                {deleting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}
                确认删除
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Checkpoint Modal */}
      <Modal
        isOpen={checkpoint !== null}
        onClose={() => setCheckpoint(null)}
        title="Checkpoint Review"
      >
        {checkpoint && (
          <div className="space-y-4">
            <Badge variant="phase">{checkpoint.phase}</Badge>
            <p className="text-sm text-aide-text-primary">
              {checkpoint.summary}
            </p>
            <div className="space-y-2">
              {checkpoint.options.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => handleCheckpointResponse(opt.value)}
                  disabled={checkpointLoading}
                  className="flex w-full items-center rounded-md border border-aide-border bg-aide-bg-tertiary px-4 py-3 text-left text-sm text-aide-text-primary transition-colors hover:border-aide-accent-blue hover:bg-aide-accent-blue/10 disabled:opacity-50"
                >
                  {checkpointLoading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <ChevronRight className="mr-2 h-4 w-4 text-aide-text-muted" />
                  )}
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </Modal>

      {/* Citation Graph Modal */}
      <Modal
        isOpen={showCitationGraph}
        onClose={() => setShowCitationGraph(false)}
        title="引用图谱"
      >
        {citationGraph && citationGraph.total_papers > 0 ? (
          <div className="space-y-4">
            <div className="text-xs text-aide-text-muted">
              共 {citationGraph.total_papers} 篇论文
              {citationGraph.edges.length > 0 && ` / ${citationGraph.edges.length} 条引用关系`}
            </div>
            <div className="rounded-md border border-aide-border bg-aide-bg-tertiary p-3 max-h-[50vh] overflow-y-auto">
              <div className="space-y-2">
                {citationGraph.nodes.map((node) => (
                  <div
                    key={node.id}
                    className={`rounded-md px-3 py-2 text-xs ${
                      citationGraph.most_cited.includes(node.id)
                        ? "bg-aide-accent-blue/10 border border-aide-accent-blue/30"
                        : "bg-aide-bg-secondary"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-aide-text-primary truncate max-w-[80%]">
                        {node.title || node.id}
                      </span>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        {node.year && <span className="text-aide-text-muted">{node.year}</span>}
                        <Badge variant="phase">{node.source || "web"}</Badge>
                      </div>
                    </div>
                    {node.authors && (
                      <p className="mt-1 text-aide-text-muted truncate">{node.authors}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
            <div className="flex justify-end">
              <Button
                variant="ghost"
                size="md"
                onClick={() => setShowCitationGraph(false)}
              >
                关闭
              </Button>
            </div>
          </div>
        ) : (
          <p className="text-sm text-aide-text-muted">暂无引用数据</p>
        )}
      </Modal>

      {/* Paper Preview Modal */}
      <Modal
        isOpen={showPaperModal}
        onClose={() => setShowPaperModal(false)}
        title="研究论文"
      >
        {paperContent && (
          <div className="space-y-4">
            {/* Token Usage Summary */}
            {tokenUsage && (
              <div className="rounded-md border border-aide-border bg-aide-bg-tertiary p-4">
                <h4 className="mb-3 text-sm font-semibold text-aide-text-primary">Token 用量统计</h4>
                <div className="grid grid-cols-4 gap-3 text-xs">
                  <div className="rounded-md bg-aide-bg-secondary p-2.5">
                    <p className="text-aide-text-muted">总 Token</p>
                    <p className="mt-1 text-base font-semibold text-aide-text-primary">
                      {tokenUsage.total_tokens.toLocaleString()}
                    </p>
                  </div>
                  <div className="rounded-md bg-aide-bg-secondary p-2.5">
                    <p className="text-aide-text-muted">调用次数</p>
                    <p className="mt-1 text-base font-semibold text-aide-text-primary">
                      {tokenUsage.total_calls}
                    </p>
                  </div>
                  <div className="rounded-md bg-aide-bg-secondary p-2.5">
                    <p className="text-aide-text-muted">费用 (USD)</p>
                    <p className="mt-1 text-base font-semibold text-aide-accent-blue">
                      ${tokenUsage.total_cost_usd.toFixed(4)}
                    </p>
                  </div>
                  <div className="rounded-md bg-aide-bg-secondary p-2.5">
                    <p className="text-aide-text-muted">费用 (RMB)</p>
                    <p className="mt-1 text-base font-semibold text-aide-accent-green">
                      ¥{tokenUsage.total_cost_rmb.toFixed(4)}
                    </p>
                  </div>
                </div>
                {/* Per-model breakdown */}
                <div className="mt-3 space-y-1">
                  {Object.entries(tokenUsage.by_model).map(([model, info]) => (
                    <div key={model} className="flex items-center justify-between text-xs text-aide-text-secondary">
                      <span className="font-mono">{model}</span>
                      <span>
                        {info.total_tokens.toLocaleString()} tokens / {info.calls} calls / ${info.cost_usd.toFixed(4)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {paperEditing ? (
              <textarea
                className="h-[60vh] w-full rounded-md border border-aide-border bg-aide-bg-tertiary p-4 font-mono text-sm text-aide-text-primary resize-none focus:outline-none focus:ring-1 focus:ring-aide-accent-blue"
                value={paperEditContent}
                onChange={(e) => setPaperEditContent(e.target.value)}
              />
            ) : (
              <div className="max-h-[60vh] overflow-y-auto rounded-md border border-aide-border bg-aide-bg-tertiary p-4">
                <Markdown className="md-content">{paperContent}</Markdown>
              </div>
            )}
            <div className="flex justify-between">
              <div className="flex gap-2">
                <Button
                  variant={paperEditing ? "primary" : "secondary"}
                  size="md"
                  onClick={() => {
                    if (paperEditing) {
                      setPaperSaving(true);
                      savePaperContent(projectId, paperEditContent)
                        .then(() => {
                          setPaperContent(paperEditContent);
                          setPaperEditing(false);
                        })
                        .catch(() => {})
                        .finally(() => setPaperSaving(false));
                    } else {
                      setPaperEditContent(paperContent || "");
                      setPaperEditing(true);
                    }
                  }}
                  disabled={paperSaving}
                >
                  {paperSaving ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <PenTool className="mr-2 h-4 w-4" />
                  )}
                  {paperEditing ? "保存" : "编辑"}
                </Button>
                {paperEditing && (
                  <Button
                    variant="ghost"
                    size="md"
                    onClick={() => setPaperEditing(false)}
                  >
                    取消
                  </Button>
                )}
              </div>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="md"
                  onClick={() => {
                    setShowPaperModal(false);
                    setPaperEditing(false);
                  }}
                >
                  关闭
                </Button>
                <Button
                  variant="secondary"
                  size="md"
                  onClick={async () => {
                    try {
                      const { html } = await getPaperHtml(projectId);
                      const w = window.open("", "_blank");
                      if (w) {
                        w.document.write(html);
                        w.document.close();
                        setTimeout(() => w.print(), 500);
                      }
                    } catch { /* fallback: ignore */ }
                  }}
                >
                  <FileText className="mr-2 h-4 w-4" />
                  导出 PDF
                </Button>
                <a
                  href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/projects/${projectId}/export/paper/download`}
                  download
                >
                  <Button variant="primary" size="md">
                    <Download className="mr-2 h-4 w-4" />
                    下载 MD
                  </Button>
                </a>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
