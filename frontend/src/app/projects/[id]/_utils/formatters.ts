import {
  Search,
  Lightbulb,
  FileText,
  BookOpen,
  PenTool,
  CheckCircle2,
  TrendingUp,
} from "lucide-react";
import type { I18nKey } from "@/lib/i18n";

export const PHASES = [
  { key: "explore", label: "phase.explore" as I18nKey, icon: Search },
  { key: "hypothesize", label: "phase.hypothesize" as I18nKey, icon: Lightbulb },
  { key: "evidence", label: "phase.evidence" as I18nKey, icon: FileText },
  { key: "compose", label: "phase.compose" as I18nKey, icon: BookOpen },
  { key: "synthesize", label: "phase.synthesize" as I18nKey, icon: TrendingUp },
  { key: "complete", label: "phase.complete" as I18nKey, icon: CheckCircle2 },
];

export const ARTIFACT_SECTIONS = [
  { type: "directions", label: "artifactSection.directions" as I18nKey, icon: Search },
  { type: "hypotheses", label: "artifactSection.hypotheses" as I18nKey, icon: Lightbulb },
  { type: "evidence_findings", label: "artifactSection.evidence_findings" as I18nKey, icon: FileText },
  { type: "outline", label: "artifactSection.outline" as I18nKey, icon: BookOpen },
  { type: "draft", label: "artifactSection.draft" as I18nKey, icon: PenTool },
  { type: "review", label: "artifactSection.review" as I18nKey, icon: CheckCircle2 },
  { type: "trend_signals", label: "artifactSection.trend_signals" as I18nKey, icon: TrendingUp },
];

export type ArtifactType = (typeof ARTIFACT_SECTIONS)[number]["type"];

/** Parse a UTC ISO timestamp from backend (may lack trailing Z). */
export function parseTS(ts: string): Date {
  if (ts && !ts.endsWith("Z") && !/[+-]\d{2}:\d{2}$/.test(ts)) {
    return new Date(ts + "Z");
  }
  return new Date(ts);
}

export function formatElapsed(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  if (totalSec < 60) return `${totalSec}s`;
  const totalMin = Math.floor(totalSec / 60);
  if (totalMin < 60) return `${totalMin}m`;
  const hours = Math.floor(totalMin / 60);
  const mins = totalMin % 60;
  if (hours < 24) return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
  const days = Math.floor(hours / 24);
  const remHours = hours % 24;
  return remHours > 0 ? `${days}d ${remHours}h` : `${days}d`;
}

export function formatDateTime(ts: string): string {
  const d = parseTS(ts);
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const h = String(d.getHours()).padStart(2, "0");
  const m = String(d.getMinutes()).padStart(2, "0");
  return `${month}-${day} ${h}:${m}`;
}

export function formatDateTimeFull(ts: string): string {
  const d = parseTS(ts);
  const y = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const h = String(d.getHours()).padStart(2, "0");
  const m = String(d.getMinutes()).padStart(2, "0");
  const s = String(d.getSeconds()).padStart(2, "0");
  return `${y}-${month}-${day} ${h}:${m}:${s}`;
}

function formatComplexItem(item: unknown): string {
  if (typeof item === "string") {
    try {
      const parsed = JSON.parse(item);
      if (typeof parsed === "object" && parsed !== null) return formatComplexItem(parsed);
    } catch { /* not JSON, use as string */ }
    return item;
  }
  if (typeof item === "object" && item !== null) {
    const obj = item as Record<string, unknown>;

    if (typeof obj.hypothesis === "string") {
      const tag = typeof obj.id === "string" ? `**${obj.id}** ` : "";
      const parts = [`${tag}${obj.hypothesis}`];
      if (typeof obj.methodology === "string") parts.push(`*方法*: ${obj.methodology}`);
      if (typeof obj.rationale === "string") parts.push(`*依据*: ${obj.rationale}`);
      if (typeof obj.expected_outcome === "string") parts.push(`*预期*: ${obj.expected_outcome}`);
      return parts.join("\n\n");
    }

    if (typeof obj.signal_type === "string") {
      const entities = Array.isArray(obj.entities) ? (obj.entities as string[]).join(", ") : "";
      const parts = [`**[${String(obj.signal_type).toUpperCase()}]** ${entities}`];
      if (typeof obj.description === "string") parts.push(obj.description);
      if (typeof obj.evidence_summary === "string") parts.push(`*${obj.evidence_summary}*`);
      if (typeof obj.confidence === "number") parts.push(`置信度 **${obj.confidence}**`);
      return parts.join("\n\n");
    }

    const parts: string[] = [];
    const skipKeys = new Set(["id", "artifact_id", "artifact_type", "created_by", "version"]);
    for (const [k, v] of Object.entries(obj)) {
      if (skipKeys.has(k)) continue;
      if (typeof v === "string") parts.push(`**${k}**: ${v}`);
      else if (Array.isArray(v)) parts.push(`**${k}**: ${(v as unknown[]).map(String).join(", ")}`);
      else if (typeof v === "number" || typeof v === "boolean") parts.push(`**${k}**: ${v}`);
    }
    return parts.join("\n\n") || JSON.stringify(item);
  }
  return String(item);
}

export function getArtifactDisplay(data: Record<string, unknown>): { main: string; sub?: string } {
  let d = data;
  if (typeof data.content === "string" && data.content.trim().startsWith("{")) {
    try { d = JSON.parse(data.content) as Record<string, unknown>; } catch { /* use d as-is */ }
  }

  if (Array.isArray(d.findings) && (d.findings as unknown[]).length > 0) {
    const lines = (d.findings as unknown[]).map(f => typeof f === "string" ? f : JSON.stringify(f));
    return { main: lines.join("\n") };
  }
  if (typeof d.title === "string" && d.title) {
    let sub = typeof d.body === "string" ? d.body : undefined;
    if (!sub) {
      const skip = new Set(["artifact_type", "artifact_id", "created_by", "version", "tags",
        "superseded", "content", "created_at", "updated_at", "active_count", "title", "body"]);
      for (const [k, v] of Object.entries(d)) {
        if (skip.has(k)) continue;
        if (Array.isArray(v) && (v as unknown[]).length > 0) {
          sub = (v as unknown[]).map(item => formatComplexItem(item)).join("\n\n---\n\n");
          break;
        }
      }
    }
    return { main: d.title, sub };
  }
  if (typeof d.hypothesis === "string" && d.hypothesis) {
    return { main: d.hypothesis, sub: typeof d.methodology === "string" ? d.methodology : undefined };
  }
  if (typeof d.score !== "undefined") {
    const weaknesses = Array.isArray(d.weaknesses) ? (d.weaknesses as unknown[]).join("\n") : "";
    const strengths = Array.isArray(d.strengths) ? (d.strengths as unknown[]).join("\n") : "";
    const sub = [strengths && `Strengths:\n${strengths}`, weaknesses && `Weaknesses:\n${weaknesses}`].filter(Boolean).join("\n\n");
    return { main: `Score: ${d.score}/10`, sub: sub || undefined };
  }
  if (Array.isArray(d.trends) && (d.trends as unknown[]).length > 0) {
    const desc = typeof d.description === "string" ? d.description : "Trend Signals";
    const lines = (d.trends as unknown[]).map(t => formatComplexItem(t));
    return { main: desc, sub: lines.join("\n\n---\n\n") };
  }
  if (typeof d.text === "string" && d.text) {
    return { main: d.text };
  }
  if (typeof d.section === "string" && d.section) {
    return { main: d.section };
  }
  const skip = new Set(["artifact_id", "artifact_type", "created_by", "version", "tags", "superseded", "content", "created_at", "updated_at", "active_count"]);
  for (const [k, v] of Object.entries(d)) {
    if (skip.has(k)) continue;
    if (typeof v === "string" && v) return { main: `${k}: ${v}` };
    if (Array.isArray(v) && (v as unknown[]).length > 0) {
      const lines = (v as unknown[]).map(item => formatComplexItem(item));
      return { main: `${k}:\n${lines.join("\n")}` };
    }
  }
  const artType = typeof data.artifact_type === "string"
    ? data.artifact_type.replace(/_/g, " ")
    : "";
  const ver = typeof data.version === "number" ? ` v${data.version}` : "";
  return { main: artType ? `(${artType}${ver} -- no content stored)` : "(no content)" };
}
