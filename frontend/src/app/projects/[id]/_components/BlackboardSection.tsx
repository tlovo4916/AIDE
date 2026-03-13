"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Markdown } from "@/components/ui/markdown";
import { useLocale } from "@/contexts/LocaleContext";
import { ARTIFACT_SECTIONS, getArtifactDisplay } from "../_utils/formatters";

const COLLAPSE_THRESHOLD = 300;

interface BlackboardSectionProps {
  artifacts: Record<string, unknown[]>;
  isLoading: boolean;
}

export function BlackboardSection({ artifacts, isLoading }: BlackboardSectionProps) {
  const { t } = useLocale();

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-aide-accent-blue border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-aide-text-muted">
        {t("section.blackboard")}
      </h2>
      <div className="space-y-8">
        {ARTIFACT_SECTIONS.map((section) => (
          <ArtifactGroup
            key={section.type}
            type={section.type}
            label={t(section.label)}
            icon={section.icon}
            items={artifacts[section.type] ?? []}
          />
        ))}
      </div>
    </div>
  );
}

function ArtifactGroup({
  type,
  label,
  icon: Icon,
  items,
}: {
  type: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  items: unknown[];
}) {
  const { t } = useLocale();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="space-y-3">
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="flex w-full items-center gap-2 text-left"
      >
        <Icon className="h-4 w-4 text-aide-text-muted" />
        <h3 className="text-sm font-medium text-aide-text-secondary">{label}</h3>
        {items.length > 0 && (
          <Badge variant="default" className="ml-1">{items.length}</Badge>
        )}
        <div className="ml-auto">
          {collapsed
            ? <ChevronDown className="h-4 w-4 text-aide-text-muted" />
            : <ChevronUp className="h-4 w-4 text-aide-text-muted" />
          }
        </div>
      </button>

      {!collapsed && (
        items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-aide-border px-4 py-6 text-center text-xs text-aide-text-muted">
            {t("empty.noArtifacts", { type: label })}
          </div>
        ) : (
          <div className="grid gap-3 lg:grid-cols-3 md:grid-cols-2">
            {items.map((item, i) => (
              <ArtifactCard key={i} item={item} />
            ))}
          </div>
        )
      )}
    </div>
  );
}

function ArtifactCard({ item }: { item: unknown }) {
  const { t } = useLocale();
  const artifact = item as { id: string; type: string; data: Record<string, unknown> };
  const { main, sub } = getArtifactDisplay(artifact.data ?? {});
  const author = typeof artifact.data?.created_by === "string" ? artifact.data.created_by : undefined;

  const totalLen = main.length + (sub?.length ?? 0);
  const collapsible = totalLen > COLLAPSE_THRESHOLD;
  const [expanded, setExpanded] = useState(false);

  return (
    <Card hoverable className="animate-slide-up">
      <CardContent className="py-3">
        {author && (
          <div className="mb-1.5">
            <Badge variant="agent">{author}</Badge>
          </div>
        )}
        <Markdown className={`md-content${collapsible && !expanded ? " line-clamp-4" : ""}`}>
          {main}
        </Markdown>
        {sub && (
          <Markdown className={`md-content md-sub mt-2${collapsible && !expanded ? " line-clamp-2" : ""}`}>
            {sub}
          </Markdown>
        )}
        {collapsible && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="mt-2 flex items-center gap-1 text-xs text-aide-accent-blue hover:opacity-70 transition-opacity"
          >
            {expanded ? (
              <><ChevronUp className="h-3 w-3" />{t("action.collapse")}</>
            ) : (
              <><ChevronDown className="h-3 w-3" />{t("action.showMore")}</>
            )}
          </button>
        )}
      </CardContent>
    </Card>
  );
}
