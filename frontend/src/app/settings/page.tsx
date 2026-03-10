"use client";

import { useEffect, useState, useCallback } from "react";
import { Save, CheckCircle2, Loader2 } from "lucide-react";
import { getSettings, updateSettings } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface SettingsData {
  deepseek_api_key: string | null;
  openrouter_api_key: string | null;
  openai_api_key: string | null;
  anthropic_api_key: string | null;
  anthropic_base_url: string;
  default_model: string;
  orchestrator_model: string;
  embedding_model: string;
  summarizer_model: string;
  enable_web_retrieval: boolean;
  semantic_scholar_api_key: string | null;
  agent_model_overrides: Record<string, string>;
}

const MODEL_OPTIONS = [
  { value: "deepseek-reasoner", label: "DeepSeek Reasoner" },
  { value: "deepseek-chat", label: "DeepSeek Chat" },
  { value: "claude-opus-4-6", label: "Claude Opus 4.6" },
  { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
  { value: "gpt", label: "GPT (via OpenRouter)" },
  { value: "opus", label: "Claude Opus (via OpenRouter)" },
  { value: "gemini-pro", label: "Gemini Pro (via OpenRouter)" },
];

const AGENT_ROLES = [
  { key: "director", label: "Director" },
  { key: "scientist", label: "Scientist" },
  { key: "librarian", label: "Librarian" },
  { key: "writer", label: "Writer" },
  { key: "critic", label: "Critic" },
  { key: "synthesizer", label: "Synthesizer" },
];

const DEFAULT_SETTINGS: SettingsData = {
  deepseek_api_key: null,
  openrouter_api_key: null,
  openai_api_key: null,
  anthropic_api_key: null,
  anthropic_base_url: "https://api.anthropic.com",
  default_model: "deepseek-reasoner",
  orchestrator_model: "deepseek-chat",
  embedding_model: "text-embedding-3-small",
  summarizer_model: "deepseek-chat",
  enable_web_retrieval: false,
  semantic_scholar_api_key: null,
  agent_model_overrides: {
    director: "deepseek-reasoner",
    scientist: "deepseek-reasoner",
    critic: "deepseek-reasoner",
    librarian: "deepseek-chat",
    writer: "deepseek-chat",
    synthesizer: "deepseek-reasoner",
  },
};

export default function SettingsPage() {
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
      await updateSettings(settings);
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

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-6 w-6 animate-spin text-aide-accent-blue" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl animate-fade-in">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight text-aide-text-primary">
          Settings
        </h1>
        <p className="mt-1 text-sm text-aide-text-secondary">
          Configure API keys, model preferences, and research defaults
        </p>
      </div>

      <div className="space-y-6">
        {/* API Keys */}
        <Card>
          <CardHeader>
            <CardTitle>API Keys</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              label="DeepSeek API Key"
              type="password"
              value={settings.deepseek_api_key ?? ""}
              onChange={(e) => updateField("deepseek_api_key", e.target.value || null)}
              placeholder="sk-..."
              togglePassword
            />
            <Input
              label="OpenRouter API Key"
              type="password"
              value={settings.openrouter_api_key ?? ""}
              onChange={(e) => updateField("openrouter_api_key", e.target.value || null)}
              placeholder="sk-or-..."
              togglePassword
            />
            <Input
              label="OpenAI API Key"
              type="password"
              value={settings.openai_api_key ?? ""}
              onChange={(e) => updateField("openai_api_key", e.target.value || null)}
              placeholder="sk-..."
              togglePassword
            />
            <Input
              label="Anthropic API Key"
              type="password"
              value={settings.anthropic_api_key ?? ""}
              onChange={(e) => updateField("anthropic_api_key", e.target.value || null)}
              placeholder="sk-ant-..."
              togglePassword
            />
            <Input
              label="Anthropic Base URL"
              value={settings.anthropic_base_url}
              onChange={(e) => updateField("anthropic_base_url", e.target.value)}
              placeholder="https://api.anthropic.com"
            />
          </CardContent>
        </Card>

        {/* Model Preferences */}
        <Card>
          <CardHeader>
            <CardTitle>Model Preferences</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-aide-text-secondary">
                Default Model
              </label>
              <select
                value={settings.default_model}
                onChange={(e) => updateField("default_model", e.target.value)}
                className="w-full rounded-md border border-aide-border bg-aide-bg-tertiary px-3 py-2 text-sm text-aide-text-primary outline-none transition-colors focus:border-aide-border-focus"
              >
                {MODEL_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1.5 block text-sm font-medium text-aide-text-secondary">
                Orchestrator Model
              </label>
              <select
                value={settings.orchestrator_model}
                onChange={(e) => updateField("orchestrator_model", e.target.value)}
                className="w-full rounded-md border border-aide-border bg-aide-bg-tertiary px-3 py-2 text-sm text-aide-text-primary outline-none transition-colors focus:border-aide-border-focus"
              >
                {MODEL_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-aide-text-secondary">
                Per-Agent Model Configuration
              </label>
              <div className="space-y-2">
                {AGENT_ROLES.map((role) => (
                  <div key={role.key} className="flex items-center gap-3">
                    <span className="w-24 text-sm text-aide-text-primary">
                      {role.label}
                    </span>
                    <select
                      value={
                        settings.agent_model_overrides[role.key] ?? ""
                      }
                      onChange={(e) =>
                        updateAgentOverride(role.key, e.target.value)
                      }
                      className="flex-1 rounded-md border border-aide-border bg-aide-bg-tertiary px-3 py-1.5 text-sm text-aide-text-primary outline-none transition-colors focus:border-aide-border-focus"
                    >
                      <option value="">Use default</option>
                      {MODEL_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Save Button */}
        <div className="flex items-center justify-end gap-3">
          {saved && (
            <span className="flex items-center gap-1.5 text-sm text-aide-accent-green animate-fade-in">
              <CheckCircle2 className="h-4 w-4" />
              Settings saved
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
            Save Settings
          </Button>
        </div>
      </div>
    </div>
  );
}
