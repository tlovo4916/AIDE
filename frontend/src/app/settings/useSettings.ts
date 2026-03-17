"use client";

import { useEffect, useState, useCallback } from "react";
import { getSettings, updateSettings } from "@/lib/api";
import {
  PRESET_OVERRIDES,
  type BuiltinPresetKey,
  type CustomPresetData,
} from "@/lib/presets";

export interface SettingsData {
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

export const DEFAULT_SETTINGS: SettingsData = {
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

export type ModelTag = "free" | "economy" | "value" | "flagship" | "premium";

export type ModelOption = {
  value: string;
  label: string;
  provider: "deepseek" | "anthropic" | "openrouter";
  tag: ModelTag;
  /** cost in USD per 1M tokens, for price warning */
  costPer1M?: number;
};

export const ALL_MODEL_OPTIONS: ModelOption[] = [
  // -- Free --
  { value: "step-3.5-flash", label: "Step 3.5 Flash (256K)", provider: "openrouter", tag: "free", costPer1M: 0 },
  // -- Economy (< $0.50/M output) --
  { value: "deepseek-chat", label: "DeepSeek Chat V3.2 (128K) [直连]", provider: "deepseek", tag: "economy", costPer1M: 0.41 },
  { value: "deepseek-reasoner", label: "DeepSeek Reasoner V3.2 (128K) [直连]", provider: "deepseek", tag: "economy", costPer1M: 0.41 },
  { value: "grok-4.1-fast", label: "Grok 4.1 Fast (2M ctx)", provider: "openrouter", tag: "economy", costPer1M: 0.50 },
  { value: "gpt-5-nano", label: "GPT-5 Nano (400K)", provider: "openrouter", tag: "economy", costPer1M: 0.40 },
  { value: "seed-1.6-flash", label: "Seed 1.6 Flash (262K)", provider: "openrouter", tag: "economy", costPer1M: 0.30 },
  { value: "glm-4.7-flash", label: "GLM-4.7 Flash (203K)", provider: "openrouter", tag: "economy", costPer1M: 0.40 },
  { value: "mimo-v2-flash", label: "MiMo V2 Flash (262K)", provider: "openrouter", tag: "economy", costPer1M: 0.29 },
  // -- Value ($0.50-$2.50/M output) --
  { value: "llama-4-maverick", label: "Llama 4 Maverick (1M)", provider: "openrouter", tag: "value", costPer1M: 0.60 },
  { value: "minimax-m2.5", label: "MiniMax M2.5 (1M, 131K out)", provider: "openrouter", tag: "value", costPer1M: 0.95 },
  { value: "deepseek-v3.2-speciale", label: "DeepSeek V3.2 Speciale (164K)", provider: "openrouter", tag: "value", costPer1M: 1.20 },
  { value: "qwen3.5-flash", label: "Qwen 3.5 Flash (1M)", provider: "openrouter", tag: "value", costPer1M: 0.40 },
  { value: "qwen3.5-plus", label: "Qwen 3.5 Plus (1M)", provider: "openrouter", tag: "value", costPer1M: 1.56 },
  { value: "kimi-k2.5", label: "Kimi K2.5 (262K)", provider: "openrouter", tag: "value", costPer1M: 2.20 },
  { value: "glm-5", label: "GLM-5 (203K)", provider: "openrouter", tag: "value", costPer1M: 2.30 },
  { value: "qwen3.5-397b", label: "Qwen 3.5 397B (262K)", provider: "openrouter", tag: "value", costPer1M: 2.34 },
  // -- Flagship (> $5/M output) --
  { value: "gemini-3.1-pro", label: "Gemini 3.1 Pro (1M)", provider: "openrouter", tag: "flagship", costPer1M: 12 },
  { value: "gpt-5.4", label: "GPT-5.4 (1M)", provider: "openrouter", tag: "flagship", costPer1M: 15 },
  { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6 (200K)", provider: "anthropic", tag: "flagship", costPer1M: 15 },
  { value: "claude-opus-4-6", label: "Claude Opus 4.6 (200K)", provider: "anthropic", tag: "premium", costPer1M: 25 },
  { value: "gpt-5.4-pro", label: "GPT-5.4 Pro (1M)", provider: "openrouter", tag: "premium", costPer1M: 180 },
];

export const EMBEDDING_MODEL_OPTIONS: ModelOption[] = [
  { value: "nvidia/llama-nemotron-embed-vl-1b-v2:free", label: "Nemotron Embed V2 (131K ctx)", provider: "openrouter", tag: "free", costPer1M: 0 },
  { value: "qwen/qwen3-embedding-8b", label: "Qwen3 Embedding 8B (32K ctx)", provider: "openrouter", tag: "economy", costPer1M: 0.01 },
  { value: "qwen/qwen3-embedding-4b", label: "Qwen3 Embedding 4B (32K ctx)", provider: "openrouter", tag: "economy", costPer1M: 0.02 },
  { value: "openai/text-embedding-3-small", label: "OpenAI Embed 3 Small (8K ctx)", provider: "openrouter", tag: "economy", costPer1M: 0.02 },
  { value: "openai/text-embedding-3-large", label: "OpenAI Embed 3 Large (8K ctx)", provider: "openrouter", tag: "value", costPer1M: 0.13 },
  { value: "google/gemini-embedding-001", label: "Gemini Embedding 001 (20K ctx)", provider: "openrouter", tag: "value", costPer1M: 0.15 },
];

export const TAG_STYLES: Record<ModelTag, string> = {
  free: "bg-aide-accent-green/15 text-aide-accent-green",
  economy: "bg-aide-accent-amber/15 text-aide-accent-amber",
  value: "bg-aide-accent-blue/15 text-aide-accent-blue",
  flagship: "bg-aide-accent-purple/15 text-aide-accent-purple",
  premium: "bg-aide-accent-red/15 text-aide-accent-red",
};

export const TAG_GROUP_ORDER: ModelTag[] = ["free", "economy", "value", "flagship", "premium"];

export function hasKey(val: string | null | undefined): boolean {
  if (!val || val.length < 3) return false;
  if (val.includes("****")) return true;
  return val.length > 4;
}

export function getAvailableModels(s: SettingsData): ModelOption[] {
  return ALL_MODEL_OPTIONS.filter((m) => {
    if (m.provider === "deepseek") return hasKey(s.deepseek_api_key);
    if (m.provider === "anthropic") return hasKey(s.anthropic_api_key);
    if (m.provider === "openrouter") return hasKey(s.openrouter_api_key);
    return false;
  });
}

export function useSettings() {
  const [settings, setSettings] = useState<SettingsData>(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

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

  return {
    settings,
    loading,
    saving,
    saved,
    handleSave,
    updateField,
    updateAgentOverride,
    applyPreset,
    saveCustomPreset,
    deleteCustomPreset,
    applyCustomPreset,
    renameCustomPreset,
    updateCustomPresetDesc,
  };
}
