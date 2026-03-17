"use client";

import { useState } from "react";
import { Sparkles, ChevronDown, ChevronUp, Plus, X } from "lucide-react";
import type { I18nKey } from "@/lib/i18n";
import {
  AGENT_ROLE_KEYS,
  PRESET_DETAILS,
  type BuiltinPresetKey,
  type PresetKey,
  type CustomPresetData,
} from "@/lib/presets";

/** Single custom preset card -- click to apply, hover X to delete, double-click name/desc to edit */
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

export type PresetButtonConfig = {
  key: BuiltinPresetKey;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  activeBorder: string;
  activeBg: string;
  hoverBorder: string;
  enabled: boolean;
};

export default function PresetSelector({
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
  presetButtons: PresetButtonConfig[];
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
        {/* Built-in presets */}
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

        {/* Custom presets */}
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

        {/* "+" add card */}
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
