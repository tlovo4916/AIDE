"use client";

import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  MessageSquare,
  Shield,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useLocale } from "@/contexts/LocaleContext";
import { formatDateTime } from "../_utils/formatters";

type ChallengeFilter = "all" | "open" | "resolved" | "dismissed";

interface MessagesSectionProps {
  messages: { id: string; role: string; content: string; timestamp: string }[];
  challenges: { id: string; from: string; message: string; resolved: boolean }[];
}

export function MessagesSection({ messages, challenges }: MessagesSectionProps) {
  const { t } = useLocale();
  const [roleFilter, setRoleFilter] = useState<string>("all");
  const [challengeFilter, setChallengeFilter] = useState<ChallengeFilter>("all");

  const roles = Array.from(new Set(messages.map((m) => m.role)));
  const filteredMessages = roleFilter === "all"
    ? messages
    : messages.filter((m) => m.role === roleFilter);

  const active = challenges.filter((c) => !c.resolved);
  const resolved = challenges.filter((c) => c.resolved);
  const filteredChallenges = challengeFilter === "all"
    ? challenges
    : challengeFilter === "open"
      ? active
      : resolved;

  return (
    <div className="animate-fade-in flex gap-6">
      {/* Messages */}
      <div className="flex-1 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-aide-text-muted" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-aide-text-muted">
              {t("section.messageStream")}
            </h2>
            <Badge variant="default">{messages.length}</Badge>
          </div>
          {roles.length > 1 && (
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="rounded-lg border border-aide-border bg-aide-bg-tertiary px-2 py-1 text-xs text-aide-text-primary outline-none"
            >
              <option value="all">{t("misc.allRoles")}</option>
              {roles.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          )}
        </div>

        {filteredMessages.length === 0 ? (
          <p className="text-sm text-aide-text-muted">{t("empty.waitingMessages")}</p>
        ) : (
          <div className="space-y-2 max-h-[70vh] overflow-y-auto">
            {filteredMessages.slice(-50).map((msg) => (
              <div
                key={msg.id}
                className="rounded-lg bg-aide-bg-tertiary px-4 py-2.5 animate-slide-up"
              >
                <div className="mb-1 flex items-center justify-between">
                  <Badge variant="agent">{msg.role}</Badge>
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

      {/* Challenges */}
      <div className="w-80 space-y-4 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-aide-text-muted" />
            <h3 className="text-sm font-semibold uppercase tracking-wider text-aide-text-muted">
              {t("section.challenges")}
            </h3>
            {active.length > 0 && <Badge variant="warning">{active.length}</Badge>}
          </div>
          <select
            value={challengeFilter}
            onChange={(e) => setChallengeFilter(e.target.value as ChallengeFilter)}
            className="rounded-lg border border-aide-border bg-aide-bg-tertiary px-2 py-1 text-xs text-aide-text-primary outline-none"
          >
            <option value="all">{t("misc.all")} ({challenges.length})</option>
            <option value="open">{t("misc.open")} ({active.length})</option>
            <option value="resolved">{t("misc.resolved")} ({resolved.length})</option>
          </select>
        </div>

        {filteredChallenges.length === 0 ? (
          <p className="text-sm text-aide-text-muted">{t("empty.noChallenges")}</p>
        ) : (
          <div className="space-y-2 max-h-[70vh] overflow-y-auto">
            {filteredChallenges.map((c) => (
              <Card
                key={c.id}
                variant={c.resolved ? "default" : "challenge"}
                className={c.resolved ? "opacity-60" : "animate-slide-up"}
              >
                <CardContent className="py-3">
                  <div className="mb-1 flex items-center gap-1.5">
                    {c.resolved ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-aide-accent-green" />
                    ) : (
                      <AlertTriangle className="h-3.5 w-3.5 text-aide-accent-amber" />
                    )}
                    <Badge variant="agent">{c.from}</Badge>
                  </div>
                  <p className={`text-xs ${c.resolved ? "text-aide-text-secondary line-through" : "text-aide-text-primary"}`}>
                    {c.message}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
