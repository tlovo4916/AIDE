"use client";

import { useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  User,
  Link2,
  Filter,
} from "lucide-react";

type ChallengeStatus = "open" | "resolved" | "dismissed";

interface EvidenceRef {
  id: string;
  label: string;
}

interface Challenge {
  id: string;
  challenger: string;
  target_artifact_id: string;
  target_artifact_label: string;
  argument: string;
  evidence_refs: EvidenceRef[];
  response: string | null;
  status: ChallengeStatus;
  created_at: string;
}

interface ChallengePanelProps {
  challenges: Challenge[];
  onSelectChallenge: (id: string) => void;
}

const STATUS_STYLES: Record<
  ChallengeStatus,
  { bg: string; text: string; label: string }
> = {
  open: { bg: "bg-amber-400/10", text: "text-amber-400", label: "Open" },
  resolved: {
    bg: "bg-green-500/10",
    text: "text-green-500",
    label: "Resolved",
  },
  dismissed: { bg: "bg-slate-700", text: "text-slate-400", label: "Dismissed" },
};

function formatTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function ChallengeCard({
  challenge,
  onSelect,
}: {
  challenge: Challenge;
  onSelect: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const style = STATUS_STYLES[challenge.status];

  return (
    <div
      className={`rounded-lg border bg-slate-800 transition-colors ${
        challenge.status === "open"
          ? "border-amber-400/30"
          : "border-slate-700"
      }`}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-start gap-3 p-3 text-left"
      >
        <AlertTriangle
          className={`mt-0.5 h-4 w-4 shrink-0 ${
            challenge.status === "open" ? "text-amber-400" : "text-slate-500"
          }`}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`rounded px-1.5 py-0.5 text-xs ${style.bg} ${style.text}`}>
              {style.label}
            </span>
            <span className="inline-flex items-center gap-1 text-xs text-slate-500">
              <User className="h-3 w-3" />
              {challenge.challenger}
            </span>
            <span className="text-xs text-slate-600">
              {formatTime(challenge.created_at)}
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-300 truncate">
            {challenge.argument}
          </p>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onSelect();
            }}
            className="mt-1 inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
          >
            <Link2 className="h-3 w-3" />
            {challenge.target_artifact_label}
          </button>
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 shrink-0 text-slate-500" />
        ) : (
          <ChevronDown className="h-4 w-4 shrink-0 text-slate-500" />
        )}
      </button>

      {expanded && (
        <div className="border-t border-slate-700 px-3 py-3 pl-10">
          <div className="space-y-3">
            <div>
              <h4 className="text-xs font-medium uppercase tracking-wider text-slate-500 mb-1">
                Argument
              </h4>
              <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
                {challenge.argument}
              </p>
            </div>

            {challenge.evidence_refs.length > 0 && (
              <div>
                <h4 className="text-xs font-medium uppercase tracking-wider text-slate-500 mb-1">
                  Evidence
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {challenge.evidence_refs.map((ref) => (
                    <span
                      key={ref.id}
                      className="inline-flex items-center gap-1 rounded bg-slate-700 px-2 py-0.5 text-xs text-slate-400"
                    >
                      <Link2 className="h-3 w-3" />
                      {ref.label}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {challenge.response && (
              <div>
                <h4 className="text-xs font-medium uppercase tracking-wider text-slate-500 mb-1">
                  Response
                </h4>
                <p className="text-sm text-slate-400 leading-relaxed whitespace-pre-wrap">
                  {challenge.response}
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ChallengePanel({
  challenges,
  onSelectChallenge,
}: ChallengePanelProps) {
  const [statusFilter, setStatusFilter] = useState<ChallengeStatus | "all">(
    "all"
  );

  const filtered =
    statusFilter === "all"
      ? challenges
      : challenges.filter((c) => c.status === statusFilter);

  const sorted = [...filtered].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  const counts = {
    all: challenges.length,
    open: challenges.filter((c) => c.status === "open").length,
    resolved: challenges.filter((c) => c.status === "resolved").length,
    dismissed: challenges.filter((c) => c.status === "dismissed").length,
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-slate-700 px-4 py-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-200">
          <AlertTriangle className="h-4 w-4 text-amber-400" />
          Challenges
          <span className="rounded-full bg-slate-700 px-2 py-0.5 text-xs tabular-nums text-slate-400">
            {counts.open} open
          </span>
        </h2>
        <div className="relative">
          <select
            value={statusFilter}
            onChange={(e) =>
              setStatusFilter(e.target.value as ChallengeStatus | "all")
            }
            className="appearance-none rounded-md border border-slate-600 bg-slate-800 py-1 pl-7 pr-8 text-xs text-slate-300 focus:border-blue-500 focus:outline-none"
          >
            <option value="all">All ({counts.all})</option>
            <option value="open">Open ({counts.open})</option>
            <option value="resolved">Resolved ({counts.resolved})</option>
            <option value="dismissed">Dismissed ({counts.dismissed})</option>
          </select>
          <Filter className="pointer-events-none absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-slate-500" />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {sorted.length === 0 && (
          <p className="py-8 text-center text-sm text-slate-600">
            No challenges match the current filter
          </p>
        )}
        {sorted.map((ch) => (
          <ChallengeCard
            key={ch.id}
            challenge={ch}
            onSelect={() => onSelectChallenge(ch.id)}
          />
        ))}
      </div>
    </div>
  );
}
