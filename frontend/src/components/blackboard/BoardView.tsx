"use client";

import { useState } from "react";
import {
  Compass,
  Lightbulb,
  FlaskConical,
  List,
  FileText,
  SearchCheck,
  ChevronDown,
  ChevronRight,
  User,
  GitBranch,
} from "lucide-react";

type ArtifactType =
  | "direction"
  | "hypothesis"
  | "evidence"
  | "outline"
  | "draft"
  | "review";

interface Artifact {
  id: string;
  type: ArtifactType;
  l0_summary: string;
  version: number;
  author_agent: string;
  active_count: number;
  status: "active" | "superseded" | "challenged";
}

interface BoardViewProps {
  artifacts: Record<string, Artifact[]>;
  onSelectArtifact: (id: string) => void;
  selectedId: string | null;
}

const TYPE_CONFIG: Record<
  ArtifactType,
  { label: string; icon: React.ComponentType<{ className?: string }> }
> = {
  direction: { label: "Directions", icon: Compass },
  hypothesis: { label: "Hypotheses", icon: Lightbulb },
  evidence: { label: "Evidence", icon: FlaskConical },
  outline: { label: "Outline", icon: List },
  draft: { label: "Draft", icon: FileText },
  review: { label: "Review", icon: SearchCheck },
};

const SECTION_ORDER: ArtifactType[] = [
  "direction",
  "hypothesis",
  "evidence",
  "outline",
  "draft",
  "review",
];

function ActiveCountDots({ count }: { count: number }) {
  const filled = Math.min(count, 5);
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: 5 }).map((_, i) => (
        <span
          key={i}
          className={`block h-1.5 w-1.5 rounded-full ${
            i < filled ? "bg-blue-400" : "bg-slate-600"
          }`}
        />
      ))}
    </div>
  );
}

function ArtifactCard({
  artifact,
  isSelected,
  onClick,
}: {
  artifact: Artifact;
  isSelected: boolean;
  onClick: () => void;
}) {
  const isSuperseded = artifact.status === "superseded";
  const isChallenged = artifact.status === "challenged";

  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-lg border p-3 transition-all duration-150 ${
        isSelected
          ? "border-blue-500 bg-slate-750 ring-1 ring-blue-500/30"
          : isChallenged
            ? "border-amber-400/60 bg-slate-800 hover:bg-slate-750"
            : "border-slate-700 bg-slate-800 hover:bg-slate-750 hover:border-slate-600"
      } ${isSuperseded ? "opacity-50" : ""}`}
    >
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <span
          className={`text-sm leading-snug ${
            isSuperseded
              ? "line-through text-slate-500"
              : "text-slate-200"
          }`}
        >
          {artifact.l0_summary}
        </span>
        <ActiveCountDots count={artifact.active_count} />
      </div>
      <div className="flex items-center gap-2 mt-2">
        <span className="inline-flex items-center gap-1 rounded bg-slate-700 px-1.5 py-0.5 text-xs text-slate-400">
          <GitBranch className="h-3 w-3" />
          v{artifact.version}
        </span>
        <span className="inline-flex items-center gap-1 rounded bg-slate-700 px-1.5 py-0.5 text-xs text-slate-400">
          <User className="h-3 w-3" />
          {artifact.author_agent}
        </span>
        {isChallenged && (
          <span className="rounded bg-amber-400/10 px-1.5 py-0.5 text-xs text-amber-400">
            Challenged
          </span>
        )}
      </div>
    </button>
  );
}

export default function BoardView({
  artifacts,
  onSelectArtifact,
  selectedId,
}: BoardViewProps) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  function toggleSection(type: string) {
    setCollapsed((prev) => ({ ...prev, [type]: !prev[type] }));
  }

  return (
    <div className="space-y-4">
      {SECTION_ORDER.map((type) => {
        const config = TYPE_CONFIG[type];
        const items = artifacts[type] ?? [];
        const isCollapsed = collapsed[type] ?? false;
        const Icon = config.icon;

        return (
          <section key={type}>
            <button
              onClick={() => toggleSection(type)}
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left transition-colors hover:bg-slate-800"
            >
              {isCollapsed ? (
                <ChevronRight className="h-4 w-4 text-slate-500" />
              ) : (
                <ChevronDown className="h-4 w-4 text-slate-500" />
              )}
              <Icon className="h-4 w-4 text-blue-400" />
              <span className="text-sm font-medium text-slate-200">
                {config.label}
              </span>
              <span className="ml-auto rounded-full bg-slate-700 px-2 py-0.5 text-xs tabular-nums text-slate-400">
                {items.length}
              </span>
            </button>
            {!isCollapsed && items.length > 0 && (
              <div className="mt-2 grid gap-2 pl-9 pr-1 sm:grid-cols-2 lg:grid-cols-3">
                {items.map((artifact) => (
                  <ArtifactCard
                    key={artifact.id}
                    artifact={artifact}
                    isSelected={selectedId === artifact.id}
                    onClick={() => onSelectArtifact(artifact.id)}
                  />
                ))}
              </div>
            )}
            {!isCollapsed && items.length === 0 && (
              <p className="mt-1 pl-9 text-xs text-slate-600">
                No artifacts yet
              </p>
            )}
          </section>
        );
      })}
    </div>
  );
}
