"use client";

import {
  Compass,
  Lightbulb,
  FlaskConical,
  PenTool,
  CheckCircle2,
  RotateCcw,
} from "lucide-react";

type PhaseName =
  | "explore"
  | "hypothesize"
  | "evidence"
  | "compose"
  | "complete";

interface Backtrack {
  from: PhaseName;
  to: PhaseName;
}

interface PhaseIndicatorProps {
  currentPhase: PhaseName;
  iterationCount: number;
  completedPhases: PhaseName[];
  backtracks: Backtrack[];
}

const PHASES: {
  key: PhaseName;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}[] = [
  { key: "explore", label: "Explore", icon: Compass },
  { key: "hypothesize", label: "Hypothesize", icon: Lightbulb },
  { key: "evidence", label: "Evidence", icon: FlaskConical },
  { key: "compose", label: "Compose", icon: PenTool },
  { key: "complete", label: "Complete", icon: CheckCircle2 },
];

export default function PhaseIndicator({
  currentPhase,
  iterationCount,
  completedPhases,
  backtracks,
}: PhaseIndicatorProps) {
  const phaseIndex = (name: PhaseName) =>
    PHASES.findIndex((p) => p.key === name);

  const currentIdx = phaseIndex(currentPhase);

  const backtrackSet = new Set(
    backtracks.map((b) => `${b.from}-${b.to}`)
  );

  return (
    <div className="relative">
      <div className="flex items-center justify-between">
        {PHASES.map((phase, idx) => {
          const isCurrent = phase.key === currentPhase;
          const isCompleted = completedPhases.includes(phase.key);
          const Icon = phase.icon;

          const hasBacktrackFrom = backtracks.some(
            (b) => phaseIndex(b.from) === idx
          );

          return (
            <div key={phase.key} className="flex items-center">
              {/* Phase Node */}
              <div className="flex flex-col items-center">
                <div
                  className={`relative flex h-10 w-10 items-center justify-center rounded-full border-2 transition-all ${
                    isCurrent
                      ? "border-blue-500 bg-blue-500/10"
                      : isCompleted
                        ? "border-green-500 bg-green-500/10"
                        : "border-slate-600 bg-slate-800"
                  }`}
                >
                  <Icon
                    className={`h-5 w-5 ${
                      isCurrent
                        ? "text-blue-400"
                        : isCompleted
                          ? "text-green-500"
                          : "text-slate-500"
                    }`}
                  />
                  {isCurrent && (
                    <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-blue-500 text-[10px] font-bold text-white">
                      {iterationCount}
                    </span>
                  )}
                  {isCurrent && (
                    <span className="absolute inset-0 animate-ping rounded-full border-2 border-blue-500 opacity-20" />
                  )}
                </div>
                <span
                  className={`mt-1.5 text-xs ${
                    isCurrent
                      ? "font-medium text-blue-400"
                      : isCompleted
                        ? "text-green-500"
                        : "text-slate-500"
                  }`}
                >
                  {phase.label}
                </span>

                {hasBacktrackFrom && (
                  <RotateCcw className="mt-1 h-3 w-3 text-amber-400" />
                )}
              </div>

              {/* Connector Line */}
              {idx < PHASES.length - 1 && (
                <div className="mx-2 flex-1">
                  <div className="relative h-px w-16">
                    <div
                      className={`absolute inset-0 ${
                        idx < currentIdx
                          ? "bg-green-500"
                          : "bg-slate-700"
                      }`}
                    />
                    {backtrackSet.has(
                      `${PHASES[idx + 1].key}-${phase.key}`
                    ) && (
                      <div className="absolute -top-3 inset-x-0 border-t-2 border-dashed border-amber-400/50 rounded" />
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
