"use client";

import { useEffect, useState } from "react";
import { Loader2, CheckCircle2, Cpu } from "lucide-react";

type SubAgentState = "running" | "completed" | "failed";

interface SubAgent {
  id: string;
  parentRole: string;
  task: string;
  status: SubAgentState;
  startedAt: string;
}

interface SubAgentStatusProps {
  subagents: SubAgent[];
}

const ROLE_COLORS: Record<string, string> = {
  director: "text-purple-400",
  scientist: "text-blue-400",
  librarian: "text-emerald-400",
  writer: "text-cyan-400",
  critic: "text-amber-400",
};

function ElapsedTime({ startedAt }: { startedAt: string }) {
  const [elapsed, setElapsed] = useState("");

  useEffect(() => {
    function update() {
      const diff = Date.now() - new Date(startedAt).getTime();
      const secs = Math.floor(diff / 1000);
      if (secs < 60) {
        setElapsed(`${secs}s`);
      } else {
        const mins = Math.floor(secs / 60);
        const remainSecs = secs % 60;
        setElapsed(`${mins}m ${remainSecs}s`);
      }
    }
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, [startedAt]);

  return (
    <span className="tabular-nums text-xs text-slate-500">{elapsed}</span>
  );
}

function SubAgentCard({ agent }: { agent: SubAgent }) {
  const [fading, setFading] = useState(false);

  useEffect(() => {
    if (agent.status === "completed") {
      const timer = setTimeout(() => setFading(true), 5000);
      return () => clearTimeout(timer);
    }
  }, [agent.status]);

  const roleColor = ROLE_COLORS[agent.parentRole] ?? "text-slate-400";

  return (
    <div
      className={`flex items-center gap-3 rounded-md border border-slate-700 bg-slate-800 px-3 py-2 transition-all duration-500 ${
        fading ? "opacity-0 scale-95" : "opacity-100"
      }`}
    >
      {agent.status === "running" ? (
        <Loader2 className="h-4 w-4 shrink-0 animate-spin text-blue-400" />
      ) : agent.status === "completed" ? (
        <CheckCircle2 className="h-4 w-4 shrink-0 text-green-500" />
      ) : (
        <span className="h-4 w-4 shrink-0 rounded-full bg-red-500/20 flex items-center justify-center">
          <span className="h-1.5 w-1.5 rounded-full bg-red-400" />
        </span>
      )}
      <div className="flex-1 min-w-0">
        <p className="truncate text-sm text-slate-300">{agent.task}</p>
        <p className={`text-xs ${roleColor}`}>{agent.parentRole}</p>
      </div>
      {agent.status === "running" && (
        <ElapsedTime startedAt={agent.startedAt} />
      )}
    </div>
  );
}

export default function SubAgentStatus({ subagents }: SubAgentStatusProps) {
  const grouped = subagents.reduce<Record<string, SubAgent[]>>((acc, sa) => {
    const key = sa.parentRole;
    if (!acc[key]) acc[key] = [];
    acc[key].push(sa);
    return acc;
  }, {});

  const activeCount = subagents.filter((s) => s.status === "running").length;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 px-1">
        <Cpu className="h-4 w-4 text-blue-400" />
        <h3 className="text-sm font-semibold text-slate-200">SubAgents</h3>
        {activeCount > 0 && (
          <span className="flex items-center gap-1 rounded-full bg-blue-500/10 px-2 py-0.5 text-xs text-blue-400">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-400" />
            {activeCount} active
          </span>
        )}
      </div>

      {Object.keys(grouped).length === 0 && (
        <p className="py-4 text-center text-xs text-slate-600">
          No active subagents
        </p>
      )}

      {Object.entries(grouped).map(([role, agents]) => (
        <div key={role} className="space-y-1.5">
          {agents.map((agent) => (
            <SubAgentCard key={agent.id} agent={agent} />
          ))}
        </div>
      ))}
    </div>
  );
}
