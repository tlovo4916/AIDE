"use client";

import { useEffect, useState, useCallback } from "react";
import { Save, CheckCircle2, Loader2 } from "lucide-react";
import { getSettings, updateSettings } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface SettingsData {
  api_keys: {
    deepseek: string;
    openrouter: string;
    openai: string;
  };
  model_preferences: {
    default_model: string;
    agent_overrides: Record<string, string>;
  };
  research_defaults: {
    checkpoint_timeout_seconds: number;
    max_iterations_per_phase: number;
  };
}

const MODEL_OPTIONS = [
  { value: "deepseek-reasoner", label: "DeepSeek V3.2 Reasoner" },
  { value: "deepseek-chat", label: "DeepSeek V3.2 Chat" },
  { value: "gpt", label: "GPT-5.3 Codex" },
  { value: "opus", label: "Claude Opus 4.6" },
  { value: "gemini-pro", label: "Gemini 3.1 Pro" },
];

const AGENT_ROLES = [
  "scout",
  "analyst",
  "critic",
  "scribe",
  "orchestrator",
];

const DEFAULT_SETTINGS: SettingsData = {
  api_keys: { deepseek: "", openrouter: "", openai: "" },
  model_preferences: { default_model: "deepseek-reasoner", agent_overrides: {} },
  research_defaults: {
    checkpoint_timeout_seconds: 300,
    max_iterations_per_phase: 10,
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

  const updateApiKey = (key: keyof SettingsData["api_keys"], value: string) => {
    setSettings((prev) => ({
      ...prev,
      api_keys: { ...prev.api_keys, [key]: value },
    }));
  };

  const updateDefaultModel = (value: string) => {
    setSettings((prev) => ({
      ...prev,
      model_preferences: { ...prev.model_preferences, default_model: value },
    }));
  };

  const updateAgentOverride = (agent: string, value: string) => {
    setSettings((prev) => ({
      ...prev,
      model_preferences: {
        ...prev.model_preferences,
        agent_overrides: {
          ...prev.model_preferences.agent_overrides,
          [agent]: value,
        },
      },
    }));
  };

  const updateResearchDefault = (
    key: keyof SettingsData["research_defaults"],
    value: number
  ) => {
    setSettings((prev) => ({
      ...prev,
      research_defaults: { ...prev.research_defaults, [key]: value },
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
              value={settings.api_keys.deepseek}
              onChange={(e) => updateApiKey("deepseek", e.target.value)}
              placeholder="sk-..."
              togglePassword
            />
            <Input
              label="OpenRouter API Key"
              type="password"
              value={settings.api_keys.openrouter}
              onChange={(e) => updateApiKey("openrouter", e.target.value)}
              placeholder="sk-or-..."
              togglePassword
            />
            <Input
              label="OpenAI API Key"
              type="password"
              value={settings.api_keys.openai}
              onChange={(e) => updateApiKey("openai", e.target.value)}
              placeholder="sk-..."
              togglePassword
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
                value={settings.model_preferences.default_model}
                onChange={(e) => updateDefaultModel(e.target.value)}
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
                Per-Agent Model Overrides
              </label>
              <div className="space-y-2">
                {AGENT_ROLES.map((role) => (
                  <div key={role} className="flex items-center gap-3">
                    <span className="w-24 text-sm capitalize text-aide-text-primary">
                      {role}
                    </span>
                    <select
                      value={
                        settings.model_preferences.agent_overrides[role] ?? ""
                      }
                      onChange={(e) =>
                        updateAgentOverride(role, e.target.value)
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

        {/* Research Defaults */}
        <Card>
          <CardHeader>
            <CardTitle>Research Defaults</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              label="Checkpoint Timeout (seconds)"
              type="number"
              value={String(
                settings.research_defaults.checkpoint_timeout_seconds
              )}
              onChange={(e) =>
                updateResearchDefault(
                  "checkpoint_timeout_seconds",
                  Number(e.target.value)
                )
              }
            />
            <Input
              label="Max Iterations Per Phase"
              type="number"
              value={String(
                settings.research_defaults.max_iterations_per_phase
              )}
              onChange={(e) =>
                updateResearchDefault(
                  "max_iterations_per_phase",
                  Number(e.target.value)
                )
              }
            />
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
