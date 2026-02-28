"use client";

import { useState, useEffect, useCallback } from "react";
import {
  ShieldCheck,
  CheckCircle2,
  Pencil,
  SkipForward,
  Clock,
  X,
  FileText,
} from "lucide-react";
import AdjustEditor from "./AdjustEditor";

interface ArtifactSummary {
  id: string;
  type: string;
  l0_summary: string;
}

interface Checkpoint {
  id: string;
  phase: string;
  reason: string;
  achievements: ArtifactSummary[];
  timeout_seconds: number;
}

type CheckpointResponse = "approve" | "adjust" | "skip";

interface CheckpointModalProps {
  checkpoint: Checkpoint;
  onRespond: (response: CheckpointResponse, feedback?: string) => void;
  onClose: () => void;
}

export default function CheckpointModal({
  checkpoint,
  onRespond,
  onClose,
}: CheckpointModalProps) {
  const [mode, setMode] = useState<"choose" | "adjust">("choose");
  const [remaining, setRemaining] = useState(checkpoint.timeout_seconds);

  useEffect(() => {
    if (remaining <= 0) {
      onRespond("skip");
      return;
    }
    const timer = setInterval(() => {
      setRemaining((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [remaining, onRespond]);

  const handleAdjustSubmit = useCallback(
    (feedback: string) => {
      onRespond("adjust", feedback);
    },
    [onRespond]
  );

  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  const progressPct = (remaining / checkpoint.timeout_seconds) * 100;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="relative mx-4 w-full max-w-2xl rounded-xl border border-slate-700 bg-slate-900 shadow-2xl">
        {/* Timer Bar */}
        <div className="h-1 w-full overflow-hidden rounded-t-xl bg-slate-800">
          <div
            className="h-full bg-blue-500 transition-all duration-1000"
            style={{ width: `${progressPct}%` }}
          />
        </div>

        {/* Header */}
        <div className="flex items-start justify-between p-6 pb-4">
          <div className="flex items-start gap-3">
            <div className="rounded-lg bg-blue-500/10 p-2.5">
              <ShieldCheck className="h-6 w-6 text-blue-400" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-100">
                Checkpoint: {checkpoint.phase}
              </h1>
              <p className="mt-1 text-sm text-slate-400">
                {checkpoint.reason}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 rounded-md bg-slate-800 px-3 py-1.5 text-sm tabular-nums text-slate-300">
              <Clock className="h-4 w-4 text-slate-500" />
              {minutes}:{seconds.toString().padStart(2, "0")}
            </span>
            <button
              onClick={onClose}
              className="rounded-md p-1 text-slate-500 hover:bg-slate-800 hover:text-slate-300 transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Achievements */}
        <div className="border-t border-slate-800 px-6 py-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Phase Achievements
          </h2>
          {checkpoint.achievements.length === 0 ? (
            <p className="text-sm text-slate-600">No artifacts produced yet</p>
          ) : (
            <div className="max-h-60 space-y-1.5 overflow-y-auto">
              {checkpoint.achievements.map((a) => (
                <div
                  key={a.id}
                  className="flex items-center gap-2 rounded-md bg-slate-800 px-3 py-2"
                >
                  <FileText className="h-3.5 w-3.5 shrink-0 text-slate-500" />
                  <span className="text-xs uppercase text-blue-400 shrink-0">
                    {a.type}
                  </span>
                  <span className="truncate text-sm text-slate-300">
                    {a.l0_summary}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="border-t border-slate-800 p-6">
          {mode === "choose" ? (
            <div className="flex gap-3">
              <button
                onClick={() => onRespond("approve")}
                className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-green-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-green-500"
              >
                <CheckCircle2 className="h-4 w-4" />
                Approve
              </button>
              <button
                onClick={() => setMode("adjust")}
                className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-2.5 text-sm font-medium text-slate-900 transition-colors hover:bg-amber-400"
              >
                <Pencil className="h-4 w-4" />
                Adjust
              </button>
              <button
                onClick={() => onRespond("skip")}
                className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-slate-700 px-4 py-2.5 text-sm font-medium text-slate-300 transition-colors hover:bg-slate-600"
              >
                <SkipForward className="h-4 w-4" />
                Skip
              </button>
            </div>
          ) : (
            <AdjustEditor
              onSubmit={handleAdjustSubmit}
              onCancel={() => setMode("choose")}
            />
          )}
        </div>
      </div>
    </div>
  );
}
