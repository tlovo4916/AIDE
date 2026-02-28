"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import {
  Play,
  Pause,
  ChevronRight,
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
} from "lucide-react";
import Link from "next/link";
import {
  getProject,
  respondToCheckpoint,
  startProject,
  pauseProject,
  resumeProject,
} from "@/lib/api";
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
  current_phase: string;
  status: string;
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
  { key: "complete", label: "Complete", icon: CheckCircle2 },
];

const ARTIFACT_SECTIONS = [
  { type: "directions", label: "Research Directions", icon: Search },
  { type: "hypotheses", label: "Hypotheses", icon: Lightbulb },
  { type: "evidence", label: "Evidence", icon: FileText },
  { type: "outline", label: "Outline", icon: BookOpen },
  { type: "draft", label: "Draft", icon: PenTool },
  { type: "review", label: "Review", icon: CheckCircle2 },
] as const;

type ArtifactType = (typeof ARTIFACT_SECTIONS)[number]["type"];

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
                  {new Date(evt.timestamp).toLocaleTimeString()}
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
          {items.map((item: unknown, i: number) => {
            const artifact = item as Record<string, string>;
            return (
              <Card key={i} variant="default" className="animate-slide-up">
                <CardContent className="py-3">
                  <p className="text-sm text-aide-text-primary">
                    {artifact.title ?? artifact.content ?? JSON.stringify(artifact)}
                  </p>
                  {artifact.summary && (
                    <p className="mt-1 text-xs text-aide-text-secondary">
                      {artifact.summary}
                    </p>
                  )}
                </CardContent>
              </Card>
            );
          })}
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
                  {new Date(msg.timestamp).toLocaleTimeString()}
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

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [agentEvents, setAgentEvents] = useState<AgentEvent[]>([]);
  const [checkpoint, setCheckpoint] = useState<Checkpoint | null>(null);
  const [checkpointLoading, setCheckpointLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const ws = useTypedWebSocket(projectId);
  const blackboard = useBlackboard(projectId);

  useEffect(() => {
    getProject(projectId)
      .then(setProject)
      .catch(() => setProject(null))
      .finally(() => setLoading(false));
  }, [projectId]);

  useEffect(() => {
    if (!ws.subscribe) return;

    const unsubs = [
      ws.subscribe("AgentActivity", (payload) => {
        setAgentEvents((prev) => [
          { id: crypto.randomUUID(), ...payload } as AgentEvent,
          ...prev,
        ]);
      }),
      ws.subscribe("CheckpointCreated", (payload) => {
        setCheckpoint(payload as unknown as Checkpoint);
      }),
      ws.subscribe("CheckpointResolved", () => {
        setCheckpoint(null);
      }),
      ws.subscribe("PhaseAdvanced", (payload) => {
        const p = payload as { phase: string };
        setProject((prev) =>
          prev ? { ...prev, current_phase: p.phase } : prev
        );
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

  return (
    <div className="animate-fade-in">
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
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="phase">
            {PHASES.find((p) => p.key === project.current_phase)?.label ??
              project.current_phase}
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

      {/* Three Column Layout */}
      <div className="grid grid-cols-[220px_1fr_260px] gap-4">
        {/* Left Column: Phase Progress + Activity */}
        <div className="space-y-6">
          <div>
            <h3 className="mb-3 px-1 text-xs font-semibold uppercase tracking-wider text-aide-text-muted">
              Phase Progress
            </h3>
            <PhaseProgress currentPhase={project.current_phase} />
          </div>
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

        {/* Right Column: Challenges + Messages */}
        <div className="space-y-6 overflow-y-auto" style={{ maxHeight: "calc(100vh - 120px)" }}>
          <ChallengePanel challenges={blackboard.challenges} />
          <MessageStream messages={blackboard.messages} />
        </div>
      </div>

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
    </div>
  );
}
