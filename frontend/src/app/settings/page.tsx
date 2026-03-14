"use client";

import { useEffect, useState, useCallback } from "react";
import { Save, CheckCircle2, Loader2, Zap, Sparkles, Crown, AlertTriangle, Gift, Star, ChevronDown, ChevronUp, Plus, X } from "lucide-react";
import { useLocale } from "@/contexts/LocaleContext";
import type { I18nKey } from "@/lib/i18n";
import { getSettings, updateSettings } from "@/lib/api";
import {
  AGENT_ROLE_KEYS,
  REASONING_ROLES,
  PRESET_OVERRIDES,
  PRESET_DETAILS,
  detectPreset,
  type PresetKey,
  type PresetConfig,
  type BuiltinPresetKey,
  type CustomPresetData,
} from "@/lib/presets";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";

interface SettingsData {
  deepseek_api_key: string | null;
  openrouter_api_key: string | null;
  anthropic_api_key: string | null;
  embedding_model: string;
  summarizer_model: string;
  enable_web_retrieval: boolean;
  semantic_scholar_api_key: string | null;
  agent_model_overrides: Record<string, string>;
  custom_presets: Record<string, CustomPresetData>;
}

type ModelTag = "free" | "economy" | "value" | "flagship" | "premium";

type ModelOption = {
  value: string;
  label: string;
  provider: "deepseek" | "anthropic" | "openrouter";
  tag: ModelTag;
  /** cost in USD per 1M tokens, for price warning */
  costPer1M?: number;
};

const ALL_MODEL_OPTIONS: ModelOption[] = [
  // ── Free ──
  { value: "step-3.5-flash", label: "Step 3.5 Flash (256K)", provider: "openrouter", tag: "free", costPer1M: 0 },
  // ── Economy (< $0.50/M output) ──
  { value: "deepseek-chat", label: "DeepSeek Chat V3.2 (128K) [直连]", provider: "deepseek", tag: "economy", costPer1M: 0.41 },
  { value: "deepseek-reasoner", label: "DeepSeek Reasoner V3.2 (128K) [直连]", provider: "deepseek", tag: "economy", costPer1M: 0.41 },
  { value: "grok-4.1-fast", label: "Grok 4.1 Fast (2M ctx)", provider: "openrouter", tag: "economy", costPer1M: 0.50 },
  { value: "gpt-5-nano", label: "GPT-5 Nano (400K)", provider: "openrouter", tag: "economy", costPer1M: 0.40 },
  { value: "seed-1.6-flash", label: "Seed 1.6 Flash (262K)", provider: "openrouter", tag: "economy", costPer1M: 0.30 },
  { value: "glm-4.7-flash", label: "GLM-4.7 Flash (203K)", provider: "openrouter", tag: "economy", costPer1M: 0.40 },
  { value: "mimo-v2-flash", label: "MiMo V2 Flash (262K)", provider: "openrouter", tag: "economy", costPer1M: 0.29 },
  // ── Value ($0.50-$2.50/M output) ──
  { value: "llama-4-maverick", label: "Llama 4 Maverick (1M)", provider: "openrouter", tag: "value", costPer1M: 0.60 },
  { value: "minimax-m2.5", label: "MiniMax M2.5 (1M, 131K out)", provider: "openrouter", tag: "value", costPer1M: 0.95 },
  { value: "deepseek-v3.2-speciale", label: "DeepSeek V3.2 Speciale (164K)", provider: "openrouter", tag: "value", costPer1M: 1.20 },
  { value: "qwen3.5-flash", label: "Qwen 3.5 Flash (1M)", provider: "openrouter", tag: "value", costPer1M: 0.40 },
  { value: "qwen3.5-plus", label: "Qwen 3.5 Plus (1M)", provider: "openrouter", tag: "value", costPer1M: 1.56 },
  { value: "kimi-k2.5", label: "Kimi K2.5 (262K)", provider: "openrouter", tag: "value", costPer1M: 2.20 },
  { value: "glm-5", label: "GLM-5 (203K)", provider: "openrouter", tag: "value", costPer1M: 2.30 },
  { value: "qwen3.5-397b", label: "Qwen 3.5 397B (262K)", provider: "openrouter", tag: "value", costPer1M: 2.34 },
  // ── Flagship (> $5/M output) ──
  { value: "gemini-3.1-pro", label: "Gemini 3.1 Pro (1M)", provider: "openrouter", tag: "flagship", costPer1M: 12 },
  { value: "gpt-5.4", label: "GPT-5.4 (1M)", provider: "openrouter", tag: "flagship", costPer1M: 15 },
  { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6 (200K)", provider: "anthropic", tag: "flagship", costPer1M: 15 },
  { value: "claude-opus-4-6", label: "Claude Opus 4.6 (200K)", provider: "anthropic", tag: "premium", costPer1M: 25 },
  { value: "gpt-5.4-pro", label: "GPT-5.4 Pro (1M)", provider: "openrouter", tag: "premium", costPer1M: 180 },
];

const EMBEDDING_MODEL_OPTIONS: ModelOption[] = [
  { value: "nvidia/llama-nemotron-embed-vl-1b-v2:free", label: "Nemotron Embed V2 (131K ctx)", provider: "openrouter", tag: "free", costPer1M: 0 },
  { value: "qwen/qwen3-embedding-8b", label: "Qwen3 Embedding 8B (32K ctx)", provider: "openrouter", tag: "economy", costPer1M: 0.01 },
  { value: "qwen/qwen3-embedding-4b", label: "Qwen3 Embedding 4B (32K ctx)", provider: "openrouter", tag: "economy", costPer1M: 0.02 },
  { value: "openai/text-embedding-3-small", label: "OpenAI Embed 3 Small (8K ctx)", provider: "openrouter", tag: "economy", costPer1M: 0.02 },
  { value: "openai/text-embedding-3-large", label: "OpenAI Embed 3 Large (8K ctx)", provider: "openrouter", tag: "value", costPer1M: 0.13 },
  { value: "google/gemini-embedding-001", label: "Gemini Embedding 001 (20K ctx)", provider: "openrouter", tag: "value", costPer1M: 0.15 },
];

const TAG_STYLES: Record<ModelTag, string> = {
  free: "bg-aide-accent-green/15 text-aide-accent-green",
  economy: "bg-aide-accent-amber/15 text-aide-accent-amber",
  value: "bg-aide-accent-blue/15 text-aide-accent-blue",
  flagship: "bg-aide-accent-purple/15 text-aide-accent-purple",
  premium: "bg-aide-accent-red/15 text-aide-accent-red",
};

/** Threshold (USD/1M completion tokens) above which we warn the user */
const PRICE_WARNING_THRESHOLD = 50;

function hasKey(val: string | null | undefined): boolean {
  if (!val || val.length < 3) return false;
  if (val.includes("****")) return true;
  return val.length > 4;
}

function getAvailableModels(s: SettingsData): ModelOption[] {
  return ALL_MODEL_OPTIONS.filter((m) => {
    if (m.provider === "deepseek") return hasKey(s.deepseek_api_key);
    if (m.provider === "anthropic") return hasKey(s.anthropic_api_key);
    if (m.provider === "openrouter") return hasKey(s.openrouter_api_key);
    return false;
  });
}

// Preset types, constants, and detectPreset imported from @/lib/presets

const DEFAULT_SETTINGS: SettingsData = {
  deepseek_api_key: null,
  openrouter_api_key: null,
  anthropic_api_key: null,
  embedding_model: "qwen/qwen3-embedding-4b",
  summarizer_model: "deepseek-chat",
  enable_web_retrieval: false,
  semantic_scholar_api_key: null,
  agent_model_overrides: { ...PRESET_OVERRIDES.economy },
  custom_presets: {},
};

const TAG_GROUP_ORDER: ModelTag[] = ["free", "economy", "value", "flagship", "premium"];

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

function ModelSelect({
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

// PresetDetail and PRESET_DETAILS imported from @/lib/presets

/** Single custom preset card — click to apply, hover X to delete, double-click name/desc to edit */
function CustomPresetCard({
  name,
  description,
  active,
  locale,
  onApply,
  onDelete,
  onRename,
  onUpdateDesc,
}: {
  name: string;
  description?: string;
  active: boolean;
  locale: "zh" | "en";
  onApply: () => void;
  onDelete: () => void;
  onRename: (newName: string) => void;
  onUpdateDesc: (desc: string) => void;
}) {
  const [editingName, setEditingName] = useState(false);
  const [editingDesc, setEditingDesc] = useState(false);
  const [nameValue, setNameValue] = useState(name);
  const [descValue, setDescValue] = useState(description ?? "");

  function commitName() {
    const trimmed = nameValue.trim();
    if (trimmed && trimmed !== name) onRename(trimmed);
    setEditingName(false);
  }

  function commitDesc() {
    onUpdateDesc(descValue.trim());
    setEditingDesc(false);
  }

  const descText = description || (locale === "zh" ? "自定义" : "Custom");

  return (
    <button
      onClick={() => !editingName && !editingDesc && onApply()}
      className={`group relative flex flex-col items-center gap-1.5 rounded-xl border-2 px-2 py-3 text-sm transition-all ${
        active
          ? "border-aide-accent-teal bg-aide-accent-teal/10 font-medium shadow-sm"
          : "border-aide-border bg-aide-bg-secondary hover:border-aide-accent-teal/50"
      }`}
    >
      {/* hover delete */}
      <span
        role="button"
        onClick={(e) => { e.stopPropagation(); onDelete(); }}
        className="absolute right-1.5 top-1.5 rounded p-0.5 text-aide-text-muted opacity-0 transition-opacity group-hover:opacity-100 hover:bg-red-500/10 hover:text-red-400"
      >
        <X className="h-3 w-3" />
      </span>
      <div className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors ${
        active ? "bg-aide-accent-teal/15" : "bg-aide-bg-tertiary group-hover:bg-aide-bg-elevated"
      }`}>
        <Sparkles className={`h-4 w-4 ${active ? "text-aide-accent-teal" : "text-aide-text-muted group-hover:text-aide-text-secondary"}`} />
      </div>
      {/* Name: double-click to edit */}
      {editingName ? (
        <input
          type="text"
          value={nameValue}
          onChange={(e) => setNameValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") commitName(); if (e.key === "Escape") setEditingName(false); }}
          onBlur={commitName}
          onClick={(e) => e.stopPropagation()}
          autoFocus
          className="w-full rounded border border-aide-accent-teal/40 bg-aide-bg-secondary px-1 py-0.5 text-center text-[13px] text-aide-text-primary outline-none"
        />
      ) : (
        <span
          onDoubleClick={(e) => { e.stopPropagation(); setNameValue(name); setEditingName(true); }}
          className={`max-w-full truncate text-[13px] ${active ? "text-aide-accent-teal" : "text-aide-text-primary"}`}
          title={locale === "zh" ? "双击改名" : "Double-click to rename"}
        >
          {name}
        </span>
      )}
      {/* Description: double-click to edit */}
      {editingDesc ? (
        <input
          type="text"
          value={descValue}
          onChange={(e) => setDescValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") commitDesc(); if (e.key === "Escape") setEditingDesc(false); }}
          onBlur={commitDesc}
          onClick={(e) => e.stopPropagation()}
          autoFocus
          placeholder={locale === "zh" ? "添加描述" : "Add note"}
          className="w-full rounded border border-aide-accent-teal/30 bg-aide-bg-secondary px-1 py-0.5 text-center text-[11px] text-aide-text-secondary outline-none"
        />
      ) : (
        <span
          onDoubleClick={(e) => { e.stopPropagation(); setDescValue(description ?? ""); setEditingDesc(true); }}
          className={`max-w-full truncate text-[11px] leading-tight ${active ? "text-aide-accent-teal opacity-80" : "text-aide-text-muted"}`}
          title={locale === "zh" ? "双击编辑描述" : "Double-click to edit"}
        >
          {descText}
        </span>
      )}
    </button>
  );
}

function PresetSection({
  presetButtons,
  activePreset,
  applyPreset,
  t,
  locale,
  customPresets,
  onApplyCustom,
  onDeleteCustom,
  onSaveCustom,
  onRenameCustom,
  onUpdateCustomDesc,
  agentOverrides,
}: {
  presetButtons: { key: BuiltinPresetKey; icon: typeof Zap; color: string; activeBorder: string; activeBg: string; hoverBorder: string; enabled: boolean }[];
  activePreset: PresetKey;
  applyPreset: (preset: BuiltinPresetKey) => void;
  t: (key: I18nKey, params?: Record<string, string | number>) => string;
  locale: "zh" | "en";
  customPresets: Record<string, CustomPresetData>;
  onApplyCustom: (name: string) => void;
  onDeleteCustom: (name: string) => void;
  onSaveCustom: (name: string) => void;
  onRenameCustom: (oldName: string, newName: string) => void;
  onUpdateCustomDesc: (name: string, desc: string) => void;
  agentOverrides: Record<string, string>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [addingCustom, setAddingCustom] = useState(false);
  const [newName, setNewName] = useState("");

  const customNames = Object.keys(customPresets);

  function isCustomActive(name: string) {
    return activePreset === "custom" &&
      AGENT_ROLE_KEYS.every((r) => agentOverrides[r] === customPresets[name]?.overrides?.[r]);
  }

  function handleSave() {
    const trimmed = newName.trim();
    if (!trimmed) return;
    onSaveCustom(trimmed);
    setNewName("");
    setAddingCustom(false);
  }

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <label className="text-sm font-medium text-aide-text-secondary">
          {t("preset.label")}
        </label>
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-xs text-aide-text-muted transition-colors hover:text-aide-text-secondary"
        >
          {expanded ? t("preset.hideDetail" as I18nKey) : t("preset.showDetail" as I18nKey)}
          {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </button>
      </div>

      {/* Unified grid: built-in + custom + "+" */}
      <div className="grid grid-cols-5 gap-2">
        {/* ── Built-in presets ── */}
        {presetButtons.map(({ key, icon: Icon, color, activeBorder, activeBg, hoverBorder, enabled }) => {
          const isActive = activePreset === key;
          const detail = PRESET_DETAILS[key];
          return (
            <button
              key={key}
              onClick={() => enabled && applyPreset(key)}
              disabled={!enabled}
              className={`group relative flex flex-col items-center gap-1.5 rounded-xl border-2 px-2 py-3 text-sm transition-all ${
                !enabled
                  ? "cursor-not-allowed border-aide-border/50 bg-aide-bg-secondary opacity-35"
                  : isActive
                    ? `${activeBorder} ${activeBg} font-medium shadow-sm`
                    : `border-aide-border bg-aide-bg-secondary ${hoverBorder}`
              }`}
            >
              <div className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors ${
                isActive && enabled ? activeBg : "bg-aide-bg-tertiary group-hover:bg-aide-bg-elevated"
              }`}>
                <Icon className={`h-4 w-4 ${isActive && enabled ? color : "text-aide-text-muted group-hover:text-aide-text-secondary"}`} />
              </div>
              <span className={`text-[13px] ${isActive && enabled ? color : "text-aide-text-primary"}`}>
                {t(`preset.${key}` as I18nKey)}
              </span>
              <span className={`text-[11px] leading-tight ${isActive && enabled ? color + " opacity-80" : "text-aide-text-muted"}`}>
                {detail.cost[locale]}
              </span>
            </button>
          );
        })}

        {/* ── Custom presets ── */}
        {customNames.map((name) => (
          <CustomPresetCard
            key={`custom-${name}`}
            name={name}
            description={customPresets[name]?.description}
            active={isCustomActive(name)}
            locale={locale}
            onApply={() => onApplyCustom(name)}
            onDelete={() => onDeleteCustom(name)}
            onRename={(newN) => onRenameCustom(name, newN)}
            onUpdateDesc={(desc) => onUpdateCustomDesc(name, desc)}
          />
        ))}

        {/* ── "+" add card ── */}
        {addingCustom ? (
          <div className="flex flex-col items-center gap-1.5 rounded-xl border-2 border-aide-accent-teal/50 bg-aide-accent-teal/5 px-2 py-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-aide-accent-teal/15">
              <Sparkles className="h-4 w-4 text-aide-accent-teal" />
            </div>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSave();
                if (e.key === "Escape") { setAddingCustom(false); setNewName(""); }
              }}
              autoFocus
              placeholder={locale === "zh" ? "预设名称" : "Name"}
              className="w-full rounded border border-aide-accent-teal/30 bg-aide-bg-secondary px-1 py-0.5 text-center text-[13px] text-aide-text-primary outline-none focus:border-aide-accent-teal"
            />
            <div className="flex gap-3">
              <button
                onClick={handleSave}
                disabled={!newName.trim()}
                className="text-[11px] font-medium text-aide-accent-teal transition-colors hover:text-aide-accent-teal/80 disabled:opacity-30"
              >
                {t("action.confirm")}
              </button>
              <button
                onClick={() => { setAddingCustom(false); setNewName(""); }}
                className="text-[11px] text-aide-text-muted transition-colors hover:text-aide-text-secondary"
              >
                {t("action.cancel")}
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setAddingCustom(true)}
            className="flex flex-col items-center justify-center gap-1.5 rounded-xl border-2 border-dashed border-aide-border px-2 py-3 text-sm transition-all hover:border-aide-accent-teal/50 hover:bg-aide-accent-teal/5"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-aide-bg-tertiary transition-colors group-hover:bg-aide-bg-elevated">
              <Plus className="h-4 w-4 text-aide-text-muted" />
            </div>
            <span className="text-[13px] text-aide-text-muted">
              {locale === "zh" ? "保存预设" : "Save"}
            </span>
            <span className="text-[11px] leading-tight text-transparent select-none">.</span>
          </button>
        )}
      </div>

      {/* Expandable detail panel */}
      {expanded && activePreset !== "custom" && (
        <div className="mt-2 animate-slide-up rounded-lg border border-aide-border bg-aide-bg-tertiary/50 px-4 py-3">
          {(() => {
            const detail = PRESET_DETAILS[activePreset as BuiltinPresetKey];
            const btn = presetButtons.find((b) => b.key === activePreset);
            if (!detail || !btn) return null;
            return (
              <div className="space-y-2 text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-aide-text-muted">{t("preset.detailCost" as I18nKey)}</span>
                  <span className={`font-semibold ${btn.color}`}>{detail.cost[locale]}</span>
                </div>
                <div>
                  <span className="text-aide-text-muted">{t("preset.detailAgents" as I18nKey)}</span>
                  <p className="mt-0.5 leading-relaxed text-aide-text-secondary">{detail.agents[locale]}</p>
                </div>
                <div>
                  <span className="text-aide-text-muted">{t("preset.detailTraits" as I18nKey)}</span>
                  <p className="mt-0.5 leading-relaxed text-aide-text-secondary">{detail.traits[locale]}</p>
                </div>
                <div className="border-t border-aide-border/50 pt-1.5">
                  <span className="text-aide-text-secondary italic">{detail.scene[locale]}</span>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {activePreset === "custom" && !customNames.some(isCustomActive) && (
        <p className="mt-1.5 text-xs text-aide-text-muted">
          {t("preset.custom")}
        </p>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const { t, locale } = useLocale();
  const [settings, setSettings] = useState<SettingsData>(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const activePreset = detectPreset(settings.agent_model_overrides, settings.embedding_model);
  const availableModels = getAvailableModels(settings);
  const availableEmbeddingModels = hasKey(settings.openrouter_api_key) ? EMBEDDING_MODEL_OPTIONS : [];

  useEffect(() => {
    getSettings()
      .then((data) => setSettings({ ...DEFAULT_SETTINGS, ...data }))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setSaved(false);
    try {
      await updateSettings(settings as unknown as Record<string, unknown>);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } finally {
      setSaving(false);
    }
  }, [settings]);

  const updateField = <K extends keyof SettingsData>(key: K, value: SettingsData[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  const updateAgentOverride = (agent: string, value: string) => {
    setSettings((prev) => ({
      ...prev,
      agent_model_overrides: {
        ...prev.agent_model_overrides,
        [agent]: value,
      },
    }));
  };

  const applyPreset = (preset: BuiltinPresetKey) => {
    const config = PRESET_OVERRIDES[preset];
    setSettings((prev) => ({
      ...prev,
      agent_model_overrides: { ...config },
      embedding_model: config.embedding,
    }));
  };

  const saveCustomPreset = (name: string) => {
    if (!name.trim()) return;
    setSettings((prev) => ({
      ...prev,
      custom_presets: {
        ...prev.custom_presets,
        [name.trim()]: {
          overrides: { ...prev.agent_model_overrides, embedding: prev.embedding_model },
        },
      },
    }));
  };

  const deleteCustomPreset = (name: string) => {
    setSettings((prev) => {
      const next = { ...prev.custom_presets };
      delete next[name];
      return { ...prev, custom_presets: next };
    });
  };

  const applyCustomPreset = (name: string) => {
    const data = settings.custom_presets[name];
    if (data) {
      setSettings((prev) => ({
        ...prev,
        agent_model_overrides: { ...data.overrides },
        embedding_model: data.overrides.embedding || prev.embedding_model,
      }));
    }
  };

  const renameCustomPreset = (oldName: string, newName: string) => {
    if (!newName.trim() || newName.trim() === oldName) return;
    setSettings((prev) => {
      const next = { ...prev.custom_presets };
      const data = next[oldName];
      if (!data) return prev;
      delete next[oldName];
      next[newName.trim()] = data;
      return { ...prev, custom_presets: next };
    });
  };

  const updateCustomPresetDesc = (name: string, description: string) => {
    setSettings((prev) => {
      const data = prev.custom_presets[name];
      if (!data) return prev;
      return {
        ...prev,
        custom_presets: {
          ...prev.custom_presets,
          [name]: { ...data, description },
        },
      };
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-6 w-6 animate-spin text-aide-accent-blue" />
      </div>
    );
  }

  const hasDeepSeek = hasKey(settings.deepseek_api_key);
  const hasOpenRouter = hasKey(settings.openrouter_api_key);
  const hasAnthropic = hasKey(settings.anthropic_api_key);

  const presetButtons: { key: BuiltinPresetKey; icon: typeof Zap; color: string; activeBorder: string; activeBg: string; hoverBorder: string; enabled: boolean }[] = [
    { key: "free", icon: Gift, color: "text-aide-accent-cyan", activeBorder: "border-aide-accent-cyan", activeBg: "bg-aide-accent-cyan/10", hoverBorder: "hover:border-aide-accent-cyan/50", enabled: hasOpenRouter },
    { key: "economy", icon: Zap, color: "text-aide-accent-green", activeBorder: "border-aide-accent-green", activeBg: "bg-aide-accent-green/10", hoverBorder: "hover:border-aide-accent-green/50", enabled: hasDeepSeek && hasOpenRouter },
    { key: "balanced", icon: Sparkles, color: "text-aide-accent-blue", activeBorder: "border-aide-accent-blue", activeBg: "bg-aide-accent-blue/10", hoverBorder: "hover:border-aide-accent-blue/50", enabled: hasDeepSeek && hasOpenRouter },
    { key: "quality", icon: Star, color: "text-aide-accent-amber", activeBorder: "border-aide-accent-amber", activeBg: "bg-aide-accent-amber/10", hoverBorder: "hover:border-aide-accent-amber/50", enabled: hasOpenRouter },
    { key: "premium", icon: Crown, color: "text-aide-accent-purple", activeBorder: "border-aide-accent-purple", activeBg: "bg-aide-accent-purple/10", hoverBorder: "hover:border-aide-accent-purple/50", enabled: hasOpenRouter && hasAnthropic },
  ];

  return (
    <div className="mx-auto max-w-2xl animate-fade-in">
      <div className="mb-8">
        <h1 className="page-title text-2xl font-semibold tracking-tight text-aide-text-primary">
          {t("section.settings")}
        </h1>
        <p className="mt-2 text-sm text-aide-text-secondary">
          {t("misc.settingsDesc")}
        </p>
      </div>

      <div className="space-y-6">
        {/* API Keys */}
        <Card hoverable className="animate-slide-up stagger-1" style={{ opacity: 0, animationFillMode: "forwards" }}>
          <CardHeader>
            <div className="flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full bg-aide-accent-blue" />
              <CardTitle>{t("section.apiKeys")}</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              label={t("settings.deepseekApiKey")}
              type="password"
              value={settings.deepseek_api_key ?? ""}
              onChange={(e) => updateField("deepseek_api_key", e.target.value || null)}
              placeholder="sk-..."
              togglePassword
            />
            <Input
              label={t("settings.openrouterApiKey")}
              type="password"
              value={settings.openrouter_api_key ?? ""}
              onChange={(e) => updateField("openrouter_api_key", e.target.value || null)}
              placeholder="sk-or-..."
              togglePassword
            />
            <Input
              label={t("settings.anthropicApiKey")}
              type="password"
              value={settings.anthropic_api_key ?? ""}
              onChange={(e) => updateField("anthropic_api_key", e.target.value || null)}
              placeholder="sk-ant-..."
              togglePassword
            />
          </CardContent>
        </Card>

        {/* Model Preferences */}
        <Card hoverable className="animate-slide-up stagger-2" style={{ opacity: 0, animationFillMode: "forwards" }}>
          <CardHeader>
            <div className="flex items-center gap-2">
              <span className="inline-block h-2 w-2 rounded-full bg-aide-accent-green" />
              <CardTitle>{t("section.modelPreferences")}</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
            {availableModels.length === 0 && (
              <p className="rounded-lg border border-dashed border-aide-border px-4 py-3 text-center text-sm text-aide-text-muted">
                {t("preset.noModels")}
              </p>
            )}

            {/* Preset Buttons (built-in + custom + "+" in one grid) */}
            <PresetSection
              presetButtons={presetButtons}
              activePreset={activePreset}
              applyPreset={applyPreset}
              t={t}
              locale={locale}
              customPresets={settings.custom_presets}
              onApplyCustom={applyCustomPreset}
              onDeleteCustom={deleteCustomPreset}
              onSaveCustom={saveCustomPreset}
              onRenameCustom={renameCustomPreset}
              onUpdateCustomDesc={updateCustomPresetDesc}
              agentOverrides={settings.agent_model_overrides}
            />

            {/* Per-Agent Model Config */}
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
          </CardContent>
        </Card>

        {/* Sticky Save Button */}
        <div className="sticky bottom-4 flex items-center justify-end gap-3 rounded-xl border border-aide-border bg-aide-bg-secondary/90 px-4 py-3 backdrop-blur-sm shadow-lg">
          {saved && (
            <span className="flex items-center gap-1.5 text-sm text-aide-accent-green animate-fade-in">
              <CheckCircle2 className="h-4 w-4" />
              {t("status.saved")}
            </span>
          )}
          <Button
            variant="primary"
            size="md"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            {t("action.saveSettings")}
          </Button>
        </div>
      </div>
    </div>
  );
}
