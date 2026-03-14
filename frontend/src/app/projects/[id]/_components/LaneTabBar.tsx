"use client";

import { Badge } from "@/components/ui/badge";
import { useLocale } from "@/contexts/LocaleContext";
import type { LaneStatus } from "@/lib/api";
import type { I18nKey } from "@/lib/i18n";
import { CheckCircle2, Loader2, AlertTriangle, Beaker } from "lucide-react";
import type { LaneState } from "../_hooks/useProjectState";

interface LaneTabBarProps {
  activeLane: number | "synthesis";
  onChangeLane: (lane: number | "synthesis") => void;
  laneStatuses: LaneStatus[];
  laneState: LaneState | null;
}

export function LaneTabBar({
  activeLane,
  onChangeLane,
  laneStatuses,
  laneState,
}: LaneTabBarProps) {
  const { t } = useLocale();
  const numLanes = laneState?.total ?? laneStatuses.length;

  if (numLanes === 0) return null;

  return (
    <div className="mb-5 flex items-center gap-1.5 overflow-x-auto rounded-xl border border-aide-border bg-aide-bg-secondary p-1.5">
      {Array.from({ length: numLanes }, (_, i) => {
        const isActive = activeLane === i;
        const status = laneStatuses.find((ls) => ls.lane === i);
        const isDone = laneState?.completed.includes(i) ?? (status?.phase === "complete");
        const isError = laneState?.errors.includes(i) ?? false;
        const phaseKey = status?.phase ?? "explore";

        return (
          <button
            key={i}
            onClick={() => onChangeLane(i)}
            className={`relative flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all duration-150 ${
              isActive
                ? "bg-aide-accent-blue/15 text-aide-accent-blue shadow-sm"
                : "text-aide-text-secondary hover:bg-aide-bg-tertiary hover:text-aide-text-primary"
            }`}
          >
            {/* Status icon */}
            {isDone ? (
              <CheckCircle2 className="h-3.5 w-3.5 text-aide-accent-green" />
            ) : isError ? (
              <AlertTriangle className="h-3.5 w-3.5 text-red-400" />
            ) : !isDone && !isError && laneState ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-aide-accent-blue" />
            ) : null}

            <span>{t("lane.tab", { n: i + 1 })}</span>

            {/* Phase badge */}
            {status && (
              <Badge variant="default" className="text-[10px] px-1.5 py-0">
                {t((`phase.${phaseKey}`) as I18nKey)}
              </Badge>
            )}

            {/* Active indicator line */}
            {isActive && (
              <span className="absolute bottom-0 left-2 right-2 h-0.5 rounded-full bg-aide-accent-blue" />
            )}
          </button>
        );
      })}

      {/* Synthesis tab */}
      <button
        onClick={() => onChangeLane("synthesis")}
        className={`relative flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all duration-150 ${
          activeLane === "synthesis"
            ? "bg-violet-500/15 text-violet-400 shadow-sm"
            : "text-aide-text-secondary hover:bg-aide-bg-tertiary hover:text-aide-text-primary"
        }`}
      >
        {laneState?.synthesizing ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-violet-400" />
        ) : (
          <Beaker className="h-3.5 w-3.5" />
        )}
        <span>{t("lane.synthesis")}</span>

        {activeLane === "synthesis" && (
          <span className="absolute bottom-0 left-2 right-2 h-0.5 rounded-full bg-violet-500" />
        )}
      </button>
    </div>
  );
}
