"use client";

import { useState, useEffect } from "react";
import { BookOpen, TrendingUp, ExternalLink } from "lucide-react";
import { PapersPanel } from "@/components/papers-panel";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { useLocale } from "@/contexts/LocaleContext";
import { type CitationGraphData } from "@/lib/api";

interface KnowledgeSectionProps {
  projectId: string;
  citationGraph: CitationGraphData | null;
  onLoadCitationGraph: () => Promise<CitationGraphData | null>;
}

export function KnowledgeSection({
  projectId,
  citationGraph,
  onLoadCitationGraph,
}: KnowledgeSectionProps) {
  const { t } = useLocale();
  const [graph, setGraph] = useState<CitationGraphData | null>(citationGraph);

  useEffect(() => {
    if (!graph) {
      onLoadCitationGraph().then((data) => { if (data) setGraph(data); });
    }
  }, []);

  return (
    <div className="animate-fade-in flex gap-6">
      {/* Papers */}
      <div className="flex-1">
        <PapersPanel projectId={projectId} />
      </div>

      {/* Citation Graph */}
      <div className="w-96 space-y-4 flex-shrink-0">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-aide-text-muted" />
          <h3 className="text-sm font-semibold uppercase tracking-wider text-aide-text-muted">
            {t("section.citationGraph")}
          </h3>
        </div>

        {graph && graph.total_papers > 0 ? (
          <div className="space-y-3">
            <div className="text-xs text-aide-text-muted">
              {graph.total_papers} {t("misc.papers")}
              {graph.edges.length > 0 && ` / ${graph.edges.length} ${t("misc.citations")}`}
            </div>
            <div className="rounded-xl border border-aide-border bg-aide-bg-tertiary p-3 max-h-[60vh] overflow-y-auto space-y-2">
              {graph.nodes.map((node) => {
                const inner = (
                  <>
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-aide-text-primary truncate max-w-[70%]">
                        {node.title || node.id}
                      </span>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        {node.year && <span className="text-aide-text-muted">{node.year}</span>}
                        <Badge variant="phase">{node.source || "web"}</Badge>
                        {node.url && (
                          <ExternalLink className="h-3 w-3 text-aide-accent-blue" />
                        )}
                      </div>
                    </div>
                    {node.authors && (
                      <p className="mt-1 text-aide-text-muted truncate">{node.authors}</p>
                    )}
                  </>
                );

                const baseClass = `rounded-lg px-3 py-2 text-xs transition-colors ${
                  graph.most_cited.includes(node.id)
                    ? "bg-aide-accent-blue/10 border border-aide-accent-blue/30"
                    : "bg-aide-bg-secondary"
                }`;

                return node.url ? (
                  <a
                    key={node.id}
                    href={node.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`${baseClass} block hover:bg-aide-accent-blue/15 cursor-pointer`}
                  >
                    {inner}
                  </a>
                ) : (
                  <div key={node.id} className={baseClass}>
                    {inner}
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-aide-border p-8 text-center">
            <BookOpen className="mx-auto h-8 w-8 text-aide-text-muted/40 mb-2" />
            <p className="text-sm text-aide-text-muted">{t("empty.noCitations")}</p>
            <p className="mt-1 text-xs text-aide-text-muted">
              {t("empty.citationsHint")}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
