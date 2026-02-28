"use client";

import { useState } from "react";
import {
  X,
  Compass,
  Lightbulb,
  FlaskConical,
  List,
  FileText,
  SearchCheck,
  User,
  Clock,
  GitBranch,
  AlertTriangle,
} from "lucide-react";

type ArtifactType =
  | "direction"
  | "hypothesis"
  | "evidence"
  | "outline"
  | "draft"
  | "review";

type ContentTab = "l0" | "l1" | "l2";

interface ArtifactVersion {
  version: number;
  created_at: string;
  author_agent: string;
  change_summary: string;
}

interface Challenge {
  id: string;
  challenger: string;
  argument_preview: string;
  status: "open" | "resolved" | "dismissed";
  created_at: string;
}

interface ArtifactFull {
  id: string;
  type: ArtifactType;
  version: number;
  author_agent: string;
  created_at: string;
  updated_at: string;
  l0_summary: string;
  l1_detail: string;
  l2_content: string;
  status: "active" | "superseded" | "challenged";
}

interface ArtifactDetailProps {
  artifact: ArtifactFull;
  versions: ArtifactVersion[];
  relatedChallenges: Challenge[];
  onClose: () => void;
}

const TYPE_ICONS: Record<
  ArtifactType,
  React.ComponentType<{ className?: string }>
> = {
  direction: Compass,
  hypothesis: Lightbulb,
  evidence: FlaskConical,
  outline: List,
  draft: FileText,
  review: SearchCheck,
};

const TYPE_LABELS: Record<ArtifactType, string> = {
  direction: "Direction",
  hypothesis: "Hypothesis",
  evidence: "Evidence",
  outline: "Outline",
  draft: "Draft",
  review: "Review",
};

const TABS: { key: ContentTab; label: string }[] = [
  { key: "l0", label: "L0 Summary" },
  { key: "l1", label: "L1 Detail" },
  { key: "l2", label: "L2 Full" },
];

function formatTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function StructuredJsonViewer({ content }: { content: string }) {
  let parsed: unknown;
  try {
    parsed = JSON.parse(content);
  } catch {
    return (
      <pre className="whitespace-pre-wrap text-sm text-slate-300">
        {content}
      </pre>
    );
  }

  return (
    <pre className="overflow-auto rounded-md bg-slate-900 p-4 text-sm text-slate-300">
      {JSON.stringify(parsed, null, 2)}
    </pre>
  );
}

function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="prose prose-invert prose-sm max-w-none">
      {content.split("\n").map((line, i) => {
        if (line.startsWith("# "))
          return (
            <h1 key={i} className="text-lg font-bold text-slate-100 mt-4 mb-2">
              {line.slice(2)}
            </h1>
          );
        if (line.startsWith("## "))
          return (
            <h2
              key={i}
              className="text-base font-semibold text-slate-200 mt-3 mb-1"
            >
              {line.slice(3)}
            </h2>
          );
        if (line.startsWith("- "))
          return (
            <li key={i} className="text-slate-300 ml-4 list-disc">
              {line.slice(2)}
            </li>
          );
        if (line.trim() === "") return <br key={i} />;
        return (
          <p key={i} className="text-slate-300 leading-relaxed">
            {line}
          </p>
        );
      })}
    </div>
  );
}

function L2Renderer({ artifact }: { artifact: ArtifactFull }) {
  const jsonTypes: ArtifactType[] = ["hypothesis", "evidence", "direction"];
  if (jsonTypes.includes(artifact.type)) {
    return <StructuredJsonViewer content={artifact.l2_content} />;
  }
  return <MarkdownContent content={artifact.l2_content} />;
}

export default function ArtifactDetail({
  artifact,
  versions,
  relatedChallenges,
  onClose,
}: ArtifactDetailProps) {
  const [activeTab, setActiveTab] = useState<ContentTab>("l0");
  const [showVersionDropdown, setShowVersionDropdown] = useState(false);
  const Icon = TYPE_ICONS[artifact.type];

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-700 bg-slate-850 shadow-xl">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-slate-700 p-4">
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-blue-500/10 p-2">
            <Icon className="h-5 w-5 text-blue-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-slate-500">
                {artifact.id}
              </span>
              <span className="text-xs uppercase tracking-wider text-blue-400">
                {TYPE_LABELS[artifact.type]}
              </span>
            </div>
            <h2 className="mt-1 text-lg font-semibold text-slate-100">
              {artifact.l0_summary}
            </h2>
            <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1">
                <User className="h-3 w-3" />
                {artifact.author_agent}
              </span>
              <span className="inline-flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {formatTime(artifact.created_at)}
              </span>
              <div className="relative">
                <button
                  onClick={() => setShowVersionDropdown(!showVersionDropdown)}
                  className="inline-flex items-center gap-1 rounded bg-slate-700 px-2 py-0.5 hover:bg-slate-600 transition-colors"
                >
                  <GitBranch className="h-3 w-3" />
                  v{artifact.version}
                </button>
                {showVersionDropdown && (
                  <div className="absolute left-0 top-full z-10 mt-1 w-64 rounded-md border border-slate-600 bg-slate-800 p-2 shadow-lg">
                    {versions.map((v) => (
                      <div
                        key={v.version}
                        className={`rounded px-2 py-1.5 text-xs ${
                          v.version === artifact.version
                            ? "bg-blue-500/10 text-blue-400"
                            : "text-slate-400 hover:bg-slate-700"
                        }`}
                      >
                        <span className="font-mono">v{v.version}</span>
                        <span className="mx-1 text-slate-600">--</span>
                        <span>{v.change_summary}</span>
                        <span className="ml-1 text-slate-600">
                          ({v.author_agent})
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded-md p-1.5 text-slate-500 hover:bg-slate-700 hover:text-slate-300 transition-colors"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Content Tabs */}
      <div className="flex border-b border-slate-700">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? "border-b-2 border-blue-500 text-blue-400"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content + Version Timeline */}
      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 overflow-y-auto p-4">
          {activeTab === "l0" && (
            <p className="text-sm leading-relaxed text-slate-300">
              {artifact.l0_summary}
            </p>
          )}
          {activeTab === "l1" && (
            <MarkdownContent content={artifact.l1_detail} />
          )}
          {activeTab === "l2" && <L2Renderer artifact={artifact} />}
        </div>

        {/* Version Timeline Sidebar */}
        <div className="w-48 shrink-0 overflow-y-auto border-l border-slate-700 p-3">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Versions
          </h3>
          <div className="relative space-y-3 pl-4">
            <div className="absolute left-1.5 top-1 bottom-1 w-px bg-slate-700" />
            {versions.map((v) => (
              <div key={v.version} className="relative">
                <span
                  className={`absolute -left-2.5 top-1 h-2 w-2 rounded-full ${
                    v.version === artifact.version
                      ? "bg-blue-500"
                      : "bg-slate-600"
                  }`}
                />
                <p className="text-xs font-mono text-slate-400">
                  v{v.version}
                </p>
                <p className="text-xs text-slate-600">
                  {formatTime(v.created_at)}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Related Challenges */}
      {relatedChallenges.length > 0 && (
        <div className="border-t border-slate-700 p-4">
          <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
            Challenges ({relatedChallenges.length})
          </h3>
          <div className="space-y-2">
            {relatedChallenges.map((ch) => (
              <div
                key={ch.id}
                className="rounded-md border border-slate-700 bg-slate-800 p-2.5 text-sm"
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded px-1.5 py-0.5 text-xs ${
                      ch.status === "open"
                        ? "bg-amber-400/10 text-amber-400"
                        : ch.status === "resolved"
                          ? "bg-green-500/10 text-green-500"
                          : "bg-slate-700 text-slate-400"
                    }`}
                  >
                    {ch.status}
                  </span>
                  <span className="text-xs text-slate-500">
                    by {ch.challenger}
                  </span>
                </div>
                <p className="mt-1 text-slate-400">{ch.argument_preview}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
