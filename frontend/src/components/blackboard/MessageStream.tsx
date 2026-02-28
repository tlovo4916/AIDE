"use client";

import { useEffect, useRef } from "react";
import {
  Radio,
  MessageCircle,
  Filter,
  ArrowDown,
  Link2,
} from "lucide-react";

type MessageType = "broadcast" | "directed";

interface MessageRef {
  id: string;
  label: string;
}

interface AgentMessage {
  id: string;
  agent: string;
  agent_role: string;
  timestamp: string;
  content: string;
  type: MessageType;
  target_agent?: string;
  refs: MessageRef[];
}

interface MessageStreamProps {
  messages: AgentMessage[];
  agentFilter: string | null;
  onAgentFilterChange: (agent: string | null) => void;
}

const ROLE_COLORS: Record<string, string> = {
  director: "bg-purple-500",
  scientist: "bg-blue-500",
  librarian: "bg-emerald-500",
  writer: "bg-cyan-500",
  critic: "bg-amber-500",
  orchestrator: "bg-rose-500",
};

function formatTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function AgentBadge({
  agent,
  role,
  size = "sm",
}: {
  agent: string;
  role: string;
  size?: "sm" | "xs";
}) {
  const dotColor = ROLE_COLORS[role] ?? "bg-slate-500";
  return (
    <span
      className={`inline-flex items-center gap-1.5 ${
        size === "sm" ? "text-sm" : "text-xs"
      }`}
    >
      <span className={`h-2 w-2 rounded-full ${dotColor}`} />
      <span className="font-medium text-slate-200">{agent}</span>
    </span>
  );
}

function MessageBubble({ message }: { message: AgentMessage }) {
  const isBroadcast = message.type === "broadcast";

  return (
    <div
      className={`group flex gap-3 px-4 py-2.5 transition-colors hover:bg-slate-800/50 ${
        isBroadcast ? "" : "pl-8"
      }`}
    >
      <div className="mt-0.5 shrink-0">
        {isBroadcast ? (
          <Radio className="h-4 w-4 text-slate-500" />
        ) : (
          <MessageCircle className="h-4 w-4 text-slate-600" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <AgentBadge
            agent={message.agent}
            role={message.agent_role}
            size="sm"
          />
          {!isBroadcast && message.target_agent && (
            <>
              <span className="text-xs text-slate-600">-&gt;</span>
              <span className="text-xs text-slate-400">
                {message.target_agent}
              </span>
            </>
          )}
          <span className="ml-auto text-xs tabular-nums text-slate-600 opacity-0 group-hover:opacity-100 transition-opacity">
            {formatTime(message.timestamp)}
          </span>
        </div>
        <p className="mt-1 text-sm leading-relaxed text-slate-300 whitespace-pre-wrap">
          {message.content}
        </p>
        {message.refs.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {message.refs.map((ref) => (
              <span
                key={ref.id}
                className="inline-flex items-center gap-1 rounded bg-slate-700/50 px-1.5 py-0.5 text-xs text-blue-400"
              >
                <Link2 className="h-3 w-3" />
                {ref.label}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function MessageStream({
  messages,
  agentFilter,
  onAgentFilterChange,
}: MessageStreamProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const prevCountRef = useRef(messages.length);

  useEffect(() => {
    if (messages.length > prevCountRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
    prevCountRef.current = messages.length;
  }, [messages.length]);

  const uniqueAgents = Array.from(
    new Map(messages.map((m) => [m.agent, m.agent_role])).entries()
  );

  const filtered = agentFilter
    ? messages.filter((m) => m.agent === agentFilter)
    : messages;

  function scrollToBottom() {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-slate-700 px-4 py-2.5">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-200">
          <Radio className="h-4 w-4 text-blue-400" />
          Messages
        </h2>
        <div className="flex items-center gap-2">
          <div className="relative">
            <select
              value={agentFilter ?? ""}
              onChange={(e) =>
                onAgentFilterChange(e.target.value || null)
              }
              className="appearance-none rounded-md border border-slate-600 bg-slate-800 py-1 pl-7 pr-8 text-xs text-slate-300 focus:border-blue-500 focus:outline-none"
            >
              <option value="">All agents</option>
              {uniqueAgents.map(([agent, role]) => (
                <option key={agent} value={agent}>
                  {agent} ({role})
                </option>
              ))}
            </select>
            <Filter className="pointer-events-none absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-slate-500" />
          </div>
          <button
            onClick={scrollToBottom}
            className="rounded-md p-1.5 text-slate-500 hover:bg-slate-700 hover:text-slate-300 transition-colors"
            title="Scroll to bottom"
          >
            <ArrowDown className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto divide-y divide-slate-800">
        {filtered.length === 0 && (
          <p className="py-8 text-center text-sm text-slate-600">
            No messages yet
          </p>
        )}
        {filtered.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
