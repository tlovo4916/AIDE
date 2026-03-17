"use client";

import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import type { I18nKey } from "@/lib/i18n";
import {
  AGENT_ROLE_KEYS,
  REASONING_ROLES,
} from "@/lib/presets";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import {
  type ModelOption,
  type ModelTag,
  type SettingsData,
  EMBEDDING_MODEL_OPTIONS,
  TAG_STYLES,
  TAG_GROUP_ORDER,
  hasKey,
  getAvailableModels,
} from "./useSettings";

/** Threshold (USD/1M completion tokens) above which we warn the user */
const PRICE_WARNING_THRESHOLD = 50;

function groupByTag(models: ModelOption[]): { tag: ModelTag; items: ModelOption[] }[] {
  const groups: { tag: ModelTag; items: ModelOption[] }[] = [];
  for (const tag of TAG_GROUP_ORDER) {
    const items = models.filter((m) => m.tag === tag);
    if (items.length > 0) groups.push({ tag, items });
  }
  return groups;
}

function formatPrice(costPer1M: number | undefined, t: (key: I18nKey) => string): string {
  if (costPer1M === undefined) return "";
  if (costPer1M === 0) return ` (${t("tag.free")})`;
  return ` ($${costPer1M}/M)`;
}

export function ModelSelect({
  value,
  onChange,
  models,
  t,
  allowEmpty,
  emptyLabel,
  className = "",
}: {
  value: string;
  onChange: (v: string) => void;
  models: ModelOption[];
  t: (key: I18nKey, params?: Record<string, string | number>) => string;
  allowEmpty?: boolean;
  emptyLabel?: string;
  className?: string;
}) {
  const [pendingModel, setPendingModel] = useState<ModelOption | null>(null);

  const handleChange = (newVal: string) => {
    const model = models.find((m) => m.value === newVal);
    if (model && model.costPer1M && model.costPer1M >= PRICE_WARNING_THRESHOLD) {
      setPendingModel(model);
      return;
    }
    onChange(newVal);
  };

  const selected = models.find((m) => m.value === value);
  const grouped = groupByTag(models);

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <select
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          className={`flex-1 rounded-lg border border-aide-border bg-aide-bg-secondary px-3 py-2 text-sm text-aide-text-primary outline-none transition-all input-focus-ring focus:border-aide-border-focus ${className}`}
        >
          {allowEmpty && <option value="">{emptyLabel}</option>}
          {grouped.map(({ tag, items }) => (
            <optgroup key={tag} label={`── ${t(`tag.${tag}` as I18nKey)} ──`}>
              {items.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}{formatPrice(opt.costPer1M, t)}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        {selected && (
          <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${TAG_STYLES[selected.tag]}`}>
            {t(`tag.${selected.tag}` as I18nKey)}
          </span>
        )}
      </div>

      <Modal isOpen={!!pendingModel} onClose={() => setPendingModel(null)} size="sm">
        <div className="flex flex-col items-center gap-4 py-2">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-aide-accent-amber/15">
            <AlertTriangle className="h-6 w-6 text-aide-accent-amber" />
          </div>
          <div className="text-center">
            <h3 className="text-base font-semibold text-aide-text-primary">
              {t("tag.priceWarningTitle" as I18nKey)}
            </h3>
            <p className="mt-2 text-sm text-aide-text-secondary">
              {pendingModel && t("tag.priceWarning", { price: String(pendingModel.costPer1M) })}
            </p>
            {pendingModel && (
              <div className="mt-3 inline-flex items-center gap-2 rounded-lg bg-aide-bg-tertiary px-3 py-1.5">
                <span className="text-sm font-medium text-aide-text-primary">{pendingModel.label}</span>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${TAG_STYLES[pendingModel.tag]}`}>
                  {t(`tag.${pendingModel.tag}` as I18nKey)}
                </span>
              </div>
            )}
          </div>
          <div className="flex w-full gap-3 pt-1">
            <Button
              variant="outline"
              size="md"
              className="flex-1"
              onClick={() => setPendingModel(null)}
            >
              {t("action.cancel")}
            </Button>
            <Button
              variant="primary"
              size="md"
              className="flex-1"
              onClick={() => {
                if (pendingModel) onChange(pendingModel.value);
                setPendingModel(null);
              }}
            >
              {t("action.confirm")}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

export default function ModelSelectSection({
  settings,
  availableModels,
  updateAgentOverride,
  updateField,
  t,
}: {
  settings: SettingsData;
  availableModels: ModelOption[];
  updateAgentOverride: (agent: string, value: string) => void;
  updateField: <K extends keyof SettingsData>(key: K, value: SettingsData[K]) => void;
  t: (key: I18nKey, params?: Record<string, string | number>) => string;
}) {
  const availableEmbeddingModels = hasKey(settings.openrouter_api_key) ? EMBEDDING_MODEL_OPTIONS : [];

  return (
    <div>
      <label className="mb-2 block text-sm font-medium text-aide-text-secondary">
        {t("section.perAgentModel")}
      </label>
      <div className="space-y-2.5">
        {AGENT_ROLE_KEYS.map((key) => (
          <div key={key} className="flex items-center gap-2">
            <span className="w-20 shrink-0 text-sm text-aide-text-primary">
              {t(`agent.${key}` as I18nKey)}
            </span>
            {REASONING_ROLES.has(key) && (
              <span className="shrink-0 rounded bg-aide-accent-purple/15 px-1.5 py-0.5 text-[10px] font-medium text-aide-accent-purple">
                R
              </span>
            )}
            <div className="flex-1">
              <ModelSelect
                value={settings.agent_model_overrides[key] ?? ""}
                onChange={(v) => updateAgentOverride(key, v)}
                models={availableModels}
                t={t}
                allowEmpty
                emptyLabel={t("form.useDefault")}
                className="py-1.5"
              />
            </div>
          </div>
        ))}
        {/* Embedding model in per-agent section */}
        <div className="flex items-center gap-2 border-t border-aide-border/50 pt-2.5">
          <span className="w-20 shrink-0 text-sm text-aide-text-primary">
            {t("form.embeddingModel")}
          </span>
          <span className="shrink-0 rounded bg-aide-accent-blue/15 px-1.5 py-0.5 text-[10px] font-medium text-aide-accent-blue">
            E
          </span>
          <div className="flex-1">
            {availableEmbeddingModels.length > 0 ? (
              <ModelSelect
                value={settings.embedding_model}
                onChange={(v) => updateField("embedding_model", v)}
                models={availableEmbeddingModels}
                t={t}
                className="py-1.5"
              />
            ) : (
              <p className="rounded-lg border border-dashed border-aide-border px-3 py-1.5 text-sm text-aide-text-muted">
                {t("preset.noModels")}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
