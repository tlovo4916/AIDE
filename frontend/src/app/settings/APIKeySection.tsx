"use client";

import type { I18nKey } from "@/lib/i18n";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { SettingsData } from "./useSettings";

export default function APIKeySection({
  settings,
  updateField,
  t,
}: {
  settings: SettingsData;
  updateField: <K extends keyof SettingsData>(key: K, value: SettingsData[K]) => void;
  t: (key: I18nKey, params?: Record<string, string | number>) => string;
}) {
  return (
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
  );
}
