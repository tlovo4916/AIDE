"use client";

import { Save, CheckCircle2, Loader2, Zap, Sparkles, Crown, Gift, Star } from "lucide-react";
import { useLocale } from "@/contexts/LocaleContext";
import { detectPreset, type BuiltinPresetKey } from "@/lib/presets";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useSettings, hasKey, getAvailableModels } from "./useSettings";
import APIKeySection from "./APIKeySection";
import PresetSelector, { type PresetButtonConfig } from "./PresetSelector";
import ModelSelectSection from "./ModelSelectSection";

export default function SettingsPage() {
  const { t, locale } = useLocale();
  const {
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
  } = useSettings();

  const activePreset = detectPreset(settings.agent_model_overrides, settings.embedding_model);
  const availableModels = getAvailableModels(settings);

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

  const presetButtons: PresetButtonConfig[] = [
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
        <APIKeySection settings={settings} updateField={updateField} t={t} />

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
            <PresetSelector
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
            <ModelSelectSection
              settings={settings}
              availableModels={availableModels}
              updateAgentOverride={updateAgentOverride}
              updateField={updateField}
              t={t}
            />
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
