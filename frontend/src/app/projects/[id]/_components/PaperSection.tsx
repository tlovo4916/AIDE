"use client";

import { useState } from "react";
import {
  PenTool,
  FileText,
  Download,
  Loader2,
  BookOpen,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Markdown } from "@/components/ui/markdown";
import { useLocale } from "@/contexts/LocaleContext";
import { savePaperContent, getPaperHtml, type ProjectTokenUsage } from "@/lib/api";

interface PaperSectionProps {
  projectId: string;
  paperContent: string | null;
  tokenUsage: ProjectTokenUsage | null;
  isCompleted: boolean;
  onPaperContentChange: (content: string) => void;
}

export function PaperSection({
  projectId,
  paperContent,
  tokenUsage,
  isCompleted,
  onPaperContentChange,
}: PaperSectionProps) {
  const { t } = useLocale();
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState("");
  const [saving, setSaving] = useState(false);

  if (!isCompleted || !paperContent) {
    return (
      <div className="animate-fade-in flex flex-col items-center justify-center py-24">
        <BookOpen className="mb-4 h-10 w-10 text-aide-accent-blue/30" />
        <h2 className="mb-1 text-lg font-medium text-aide-text-primary">
          {t("empty.researchInProgress")}
        </h2>
        <p className="text-sm text-aide-text-secondary">
          {t("empty.paperWhenComplete")}
        </p>
      </div>
    );
  }

  async function handleSave() {
    setSaving(true);
    try {
      await savePaperContent(projectId, editContent);
      onPaperContentChange(editContent);
      setEditing(false);
    } catch { /* ignore */ }
    finally { setSaving(false); }
  }

  return (
    <div className="animate-fade-in space-y-6">
      {/* Token Usage */}
      {tokenUsage && (
        <Card>
          <CardContent className="py-4">
            <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-aide-text-muted">
              {t("section.tokenUsage")}
            </h4>
            <div className="grid grid-cols-4 gap-3 text-xs">
              <div className="rounded-lg bg-aide-bg-tertiary p-2.5">
                <p className="text-aide-text-muted">{t("misc.tokens")}</p>
                <p className="mt-1 text-base font-semibold text-aide-text-primary">
                  {tokenUsage.total_tokens.toLocaleString()}
                </p>
              </div>
              <div className="rounded-lg bg-aide-bg-tertiary p-2.5">
                <p className="text-aide-text-muted">{t("misc.calls")}</p>
                <p className="mt-1 text-base font-semibold text-aide-text-primary">
                  {tokenUsage.total_calls}
                </p>
              </div>
              <div className="rounded-lg bg-aide-bg-tertiary p-2.5">
                <p className="text-aide-text-muted">USD</p>
                <p className="mt-1 text-base font-semibold text-aide-accent-blue">
                  ${tokenUsage.total_cost_usd.toFixed(4)}
                </p>
              </div>
              <div className="rounded-lg bg-aide-bg-tertiary p-2.5">
                <p className="text-aide-text-muted">RMB</p>
                <p className="mt-1 text-base font-semibold text-aide-accent-green">
                  ¥{tokenUsage.total_cost_rmb.toFixed(4)}
                </p>
              </div>
            </div>
            {/* Per-model breakdown */}
            <div className="mt-3 space-y-1">
              {Object.entries(tokenUsage.by_model).map(([model, info]) => (
                <div key={model} className="flex items-center justify-between text-xs text-aide-text-secondary">
                  <span className="font-mono">{model}</span>
                  <span>
                    {info.total_tokens.toLocaleString()} tokens / {info.calls} calls / ${info.cost_usd.toFixed(4)}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-aide-text-muted">
          {t("section.researchPaper")}
        </h2>
        <div className="flex gap-2">
          <Button
            variant={editing ? "primary" : "outline"}
            size="sm"
            onClick={() => {
              if (editing) {
                handleSave();
              } else {
                setEditContent(paperContent || "");
                setEditing(true);
              }
            }}
            disabled={saving}
          >
            {saving ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <PenTool className="mr-1.5 h-3.5 w-3.5" />
            )}
            {editing ? t("action.save") : t("action.edit")}
          </Button>
          {editing && (
            <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
              {t("action.cancel")}
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={async () => {
              try {
                const { html } = await getPaperHtml(projectId);
                const w = window.open("", "_blank");
                if (w) {
                  w.document.write(html);
                  w.document.close();
                  setTimeout(() => w.print(), 500);
                }
              } catch { /* fallback: ignore */ }
            }}
          >
            <FileText className="mr-1.5 h-3.5 w-3.5" />
            PDF
          </Button>
          <a
            href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/projects/${projectId}/export/paper/download`}
            download
          >
            <Button variant="primary" size="sm">
              <Download className="mr-1.5 h-3.5 w-3.5" />
              {t("action.download")}
            </Button>
          </a>
        </div>
      </div>

      {/* Content */}
      {editing ? (
        <textarea
          className="h-[70vh] w-full rounded-xl border border-aide-border bg-aide-bg-tertiary p-6 font-mono text-sm text-aide-text-primary resize-none focus:outline-none input-focus-ring"
          value={editContent}
          onChange={(e) => setEditContent(e.target.value)}
        />
      ) : (
        <div className="rounded-xl border border-aide-border bg-aide-bg-tertiary p-6 max-h-[70vh] overflow-y-auto">
          <Markdown className="md-content">{paperContent}</Markdown>
        </div>
      )}
    </div>
  );
}
