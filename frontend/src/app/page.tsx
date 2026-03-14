"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Plus, FlaskConical, Calendar, Clock, Loader2, Trash2, Zap, Sparkles, Crown, Gift, Star } from "lucide-react";
import { listProjects, createProject, deleteProject, getSettings, type CreateProjectPayload } from "@/lib/api";
import {
  PRESET_OVERRIDES,
  PRESET_DETAILS,
  AGENT_ROLE_KEYS,
  type BuiltinPresetKey,
  type PresetConfig,
  type CustomPresetData,
} from "@/lib/presets";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { useLocale } from "@/contexts/LocaleContext";
import type { I18nKey } from "@/lib/i18n";

interface Project {
  id: string;
  name: string;
  research_topic: string;
  phase: string;
  status: string;
  created_at: string;
}

const PHASE_KEYS: Record<string, I18nKey> = {
  explore: "phase.explore",
  hypothesize: "phase.hypothesize",
  evidence: "phase.evidence",
  compose: "phase.compose",
  synthesize: "phase.synthesize",
  complete: "phase.complete",
};

const STATUS_KEYS: Record<string, I18nKey> = {
  running: "status.running",
  paused: "status.paused",
  completed: "status.completed",
  failed: "status.failed",
};

const STATUS_VARIANT: Record<string, "success" | "warning" | "default"> = {
  running: "success",
  paused: "warning",
  completed: "default",
  failed: "default",
};

export default function DashboardPage() {
  const router = useRouter();
  const { t } = useLocale();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null);

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch(() => setProjects([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="animate-fade-in">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="page-title text-2xl font-semibold tracking-tight text-aide-text-primary">
            {t("section.researchProjects")}
          </h1>
          <p className="mt-2 text-sm text-aide-text-secondary">
            {t("misc.manageDesc")}
          </p>
        </div>
        <Button variant="primary" size="md" onClick={() => setShowModal(true)}>
          <Plus className="mr-2 h-4 w-4" />
          {t("action.newProject")}
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-6 w-6 animate-spin text-aide-accent-blue" />
        </div>
      ) : projects.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-aide-border py-24 bg-gradient-to-b from-aide-accent-blue/5 to-transparent">
          <FlaskConical className="mb-4 h-10 w-10 text-aide-accent-blue/40" />
          <h2 className="mb-1 text-lg font-medium text-aide-text-primary">
            {t("empty.noProjects")}
          </h2>
          <p className="mb-6 text-sm text-aide-text-secondary">
            {t("empty.noProjectsHint")}
          </p>
          <Button variant="primary" size="md" onClick={() => setShowModal(true)}>
            <Plus className="mr-2 h-4 w-4" />
            {t("action.newProject")}
          </Button>
        </div>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project, idx) => (
            <div
              key={project.id}
              className={`relative group animate-slide-up stagger-${Math.min(idx + 1, 5)}`}
              style={{ opacity: 0, animationFillMode: "forwards" }}
            >
              <Link href={`/projects/${project.id}`}>
                <Card
                  hoverable
                  className={`cursor-pointer ${
                    project.status === "running"
                      ? "border-l-2 border-l-aide-accent-blue"
                      : ""
                  }`}
                >
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <CardTitle className="pr-7">{project.name}</CardTitle>
                      <Badge
                        variant={STATUS_VARIANT[project.status] ?? "default"}
                        className={project.status === "running" ? "animate-pulse-subtle" : ""}
                      >
                        {t(STATUS_KEYS[project.status] ?? "status.idle")}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="mb-4 line-clamp-2 text-sm text-aide-text-secondary">
                      {project.research_topic}
                    </p>
                    <div className="flex items-center justify-between">
                      <Badge variant="phase">
                        {t(PHASE_KEYS[project.phase] ?? "phase.explore")}
                      </Badge>
                      <div className="flex flex-col items-end gap-0.5">
                        <span className="flex items-center gap-1 text-xs text-aide-text-muted">
                          <Calendar className="h-3 w-3" />
                          {new Date(
                            project.created_at.endsWith("Z") ? project.created_at : project.created_at + "Z"
                          ).toLocaleDateString()}
                        </span>
                        {project.status === "running" && (
                          <span className="flex items-center gap-1 text-xs text-aide-accent-blue">
                            <Clock className="h-3 w-3 animate-pulse" />
                            {t("status.running")}
                          </span>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </Link>
              <button
                onClick={(e) => { e.preventDefault(); setDeleteTarget(project); }}
                className="absolute right-3 top-3 rounded-lg p-1 text-aide-text-muted opacity-0 transition-opacity group-hover:opacity-100 hover:bg-red-500/10 hover:text-red-400"
                title={t("action.deleteProject")}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      <CreateProjectModal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        onCreate={(id) => router.push(`/projects/${id}`)}
      />

      <DeleteConfirmModal
        project={deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onDeleted={(id) => setProjects((prev) => prev.filter((p) => p.id !== id))}
      />
    </div>
  );
}

/* ─── Create Project Modal ─────────────────────────────────────── */

type PresetOption = BuiltinPresetKey | string;

const PRESET_BUTTON_CONFIG: { key: BuiltinPresetKey; icon: typeof Zap; color: string; border: string; bg: string }[] = [
  { key: "free", icon: Gift, color: "text-aide-accent-cyan", border: "border-aide-accent-cyan", bg: "bg-aide-accent-cyan/10" },
  { key: "economy", icon: Zap, color: "text-aide-accent-green", border: "border-aide-accent-green", bg: "bg-aide-accent-green/10" },
  { key: "balanced", icon: Sparkles, color: "text-aide-accent-blue", border: "border-aide-accent-blue", bg: "bg-aide-accent-blue/10" },
  { key: "quality", icon: Star, color: "text-aide-accent-amber", border: "border-aide-accent-amber", bg: "bg-aide-accent-amber/10" },
  { key: "premium", icon: Crown, color: "text-aide-accent-purple", border: "border-aide-accent-purple", bg: "bg-aide-accent-purple/10" },
];

function PresetPicker({
  value,
  onChange,
  label,
  customPresets,
  locale,
  t,
}: {
  value: PresetOption;
  onChange: (v: PresetOption) => void;
  label?: string;
  customPresets: Record<string, CustomPresetData>;
  locale: "zh" | "en";
  t: (key: I18nKey, params?: Record<string, string | number>) => string;
}) {
  return (
    <div>
      {label && (
        <label className="mb-1.5 block text-sm font-medium text-aide-text-secondary">{label}</label>
      )}
      <div className="flex flex-wrap gap-1.5">
        {/* Built-in presets */}
        {PRESET_BUTTON_CONFIG.map(({ key, icon: Icon, color, border, bg }) => {
          const isActive = value === key;
          const detail = PRESET_DETAILS[key];
          return (
            <button
              key={key}
              onClick={() => onChange(key)}
              className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition-all ${
                isActive
                  ? `${border} ${bg} font-medium ${color}`
                  : `border-aide-border bg-aide-bg-secondary text-aide-text-primary hover:border-aide-primary/40`
              }`}
              title={detail.agents[locale]}
            >
              <Icon className={`h-3 w-3 ${isActive ? color : "text-aide-text-muted"}`} />
              {t(`preset.${key}` as I18nKey)}
              <span className={`text-[10px] ${isActive ? color + " opacity-70" : "text-aide-text-muted"}`}>
                {detail.cost[locale]}
              </span>
            </button>
          );
        })}
        {/* Custom presets */}
        {Object.keys(customPresets).map((cpName) => {
          const desc = customPresets[cpName]?.description;
          return (
            <button
              key={`custom-${cpName}`}
              onClick={() => onChange(cpName)}
              className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition-all ${
                value === cpName
                  ? "border-aide-accent-teal bg-aide-accent-teal/10 font-medium text-aide-accent-teal"
                  : "border-aide-border bg-aide-bg-secondary text-aide-text-primary hover:border-aide-accent-teal/40"
              }`}
            >
              <Sparkles className={`h-3 w-3 ${value === cpName ? "text-aide-accent-teal" : "text-aide-text-muted"}`} />
              {cpName}
              {desc && (
                <span className={`text-[10px] ${value === cpName ? "text-aide-accent-teal opacity-70" : "text-aide-text-muted"}`}>
                  {desc}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function CreateProjectModal({
  isOpen,
  onClose,
  onCreate,
}: {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (id: string) => void;
}) {
  const { t, locale } = useLocale();
  const [name, setName] = useState("");
  const [topic, setTopic] = useState("");
  const [concurrency, setConcurrency] = useState(1);
  const [creating, setCreating] = useState(false);

  // Preset selection: a builtin preset key or custom preset name
  const [globalPreset, setGlobalPreset] = useState<PresetOption>("economy");
  // Per-lane overrides (only used when concurrency > 1 and user wants different presets per lane)
  const [lanePresets, setLanePresets] = useState<PresetOption[]>([]);
  const [perLaneMode, setPerLaneMode] = useState(false);
  const [customPresets, setCustomPresets] = useState<Record<string, CustomPresetData>>({});

  // Fetch custom presets from settings on open
  useEffect(() => {
    if (isOpen) {
      getSettings()
        .then((data) => {
          const cp = (data as Record<string, unknown>).custom_presets;
          if (cp && typeof cp === "object") {
            setCustomPresets(cp as Record<string, CustomPresetData>);
          }
        })
        .catch(() => {});
    }
  }, [isOpen]);

  // Sync lane presets array length with concurrency
  useEffect(() => {
    setLanePresets((prev) => {
      const arr = [...prev];
      while (arr.length < concurrency) arr.push(globalPreset);
      return arr.slice(0, concurrency);
    });
  }, [concurrency, globalPreset]);

  function resolveConfig(presetKey: PresetOption): { agents: PresetConfig; embedding?: string } | null {
    if (presetKey in PRESET_OVERRIDES) {
      const preset = PRESET_OVERRIDES[presetKey as BuiltinPresetKey];
      return { agents: preset, embedding: preset.embedding };
    }
    if (presetKey in customPresets) {
      const ov = customPresets[presetKey].overrides;
      return { agents: ov, embedding: ov.embedding };
    }
    return null;
  }

  async function handleCreate() {
    if (!name.trim() || !topic.trim()) return;
    setCreating(true);
    try {
      // Build lane_overrides array and extract embedding model
      let laneOverrides: Record<string, string>[] | undefined;
      let embeddingModel: string | undefined;
      if (concurrency <= 1) {
        const resolved = resolveConfig(globalPreset);
        if (resolved) {
          laneOverrides = [resolved.agents];
          embeddingModel = resolved.embedding;
        }
      } else if (perLaneMode) {
        laneOverrides = lanePresets.map((lp) => {
          const r = resolveConfig(lp);
          return r ? r.agents : {};
        });
        // Use first lane's embedding as project-level default
        const firstResolved = resolveConfig(lanePresets[0] ?? "");
        embeddingModel = firstResolved?.embedding;
      } else {
        const resolved = resolveConfig(globalPreset);
        if (resolved) {
          laneOverrides = Array(concurrency).fill(resolved.agents);
          embeddingModel = resolved.embedding;
        }
      }

      const configJson: Record<string, unknown> = {};
      if (laneOverrides) configJson.lane_overrides = laneOverrides;
      if (embeddingModel) configJson.embedding_model = embeddingModel;

      const { id } = await createProject({
        name: name.trim(),
        research_topic: topic.trim(),
        concurrency,
        config_json: Object.keys(configJson).length > 0 ? configJson as CreateProjectPayload["config_json"] : undefined,
      });
      onCreate(id);
    } finally {
      setCreating(false);
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={t("modal.newProject")} size="lg">
      <div className="space-y-4">
        <Input
          label={t("form.projectName")}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("form.projectNamePlaceholder")}
        />
        <Input
          label={t("form.researchTopic")}
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder={t("form.researchTopicPlaceholder")}
        />

        {/* Model Preset */}
        <PresetPicker
          value={globalPreset}
          onChange={(v) => {
            setGlobalPreset(v);
            if (!perLaneMode) {
              setLanePresets((prev) => prev.map(() => v));
            }
          }}
          label={t("preset.selectForProject" as I18nKey)}
          customPresets={customPresets}
          locale={locale}
          t={t}
        />

        {/* Concurrency slider */}
        <div>
          <label className="mb-1 block text-sm font-medium text-aide-text-secondary">
            {t("form.parallelLanes")} ({concurrency})
          </label>
          <input
            type="range"
            min={1}
            max={5}
            value={concurrency}
            onChange={(e) => setConcurrency(Number(e.target.value))}
            className="w-full accent-aide-accent-blue"
          />
          <div className="mt-1 flex justify-between text-xs text-aide-text-muted">
            <span>{t("form.sequential")}</span>
            <span>{t("form.maxParallel")}</span>
          </div>
        </div>

        {/* Per-lane preset overrides (only when concurrency > 1) */}
        {concurrency > 1 && (
          <div>
            <label className="mb-1.5 flex items-center gap-2 text-sm font-medium text-aide-text-secondary">
              <input
                type="checkbox"
                checked={perLaneMode}
                onChange={(e) => {
                  setPerLaneMode(e.target.checked);
                  if (!e.target.checked) {
                    setLanePresets((prev) => prev.map(() => globalPreset));
                  }
                }}
                className="rounded accent-aide-primary"
              />
              {locale === "zh" ? "各通道使用不同预设" : "Different preset per lane"}
            </label>
            {perLaneMode && (
              <div className="mt-2 space-y-2 rounded-lg border border-aide-border bg-aide-bg-tertiary/50 p-3">
                {Array.from({ length: concurrency }, (_, i) => (
                  <PresetPicker
                    key={i}
                    value={lanePresets[i] ?? ""}
                    onChange={(v) => {
                      setLanePresets((prev) => {
                        const next = [...prev];
                        next[i] = v;
                        return next;
                      });
                    }}
                    label={t("preset.perLane" as I18nKey, { lane: String(i + 1) })}
                    customPresets={customPresets}
                    locale={locale}
                    t={t}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" size="md" onClick={onClose}>{t("action.cancel")}</Button>
        <Button
          variant="primary"
          size="md"
          onClick={handleCreate}
          disabled={creating || !name.trim() || !topic.trim()}
        >
          {creating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
          {t("action.create")}
        </Button>
      </div>
    </Modal>
  );
}

/* ─── Delete Confirm Modal ────────────────────────────────────── */

function DeleteConfirmModal({
  project,
  onClose,
  onDeleted,
}: {
  project: Project | null;
  onClose: () => void;
  onDeleted: (id: string) => void;
}) {
  const { t } = useLocale();
  const [deleting, setDeleting] = useState(false);

  if (!project) return null;

  async function handleDelete() {
    if (!project) return;
    setDeleting(true);
    try {
      await deleteProject(project.id);
      onDeleted(project.id);
      onClose();
    } finally {
      setDeleting(false);
    }
  }

  return (
    <Modal isOpen={true} onClose={onClose} title={t("modal.deleteProject")} size="sm">
      <p className="text-sm text-aide-text-secondary">
        {t("modal.deleteConfirm", { name: project.name })}
      </p>
      <p className="mt-1 text-xs text-aide-text-muted">
        {t("modal.deleteWarning")}
      </p>
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" size="md" onClick={onClose} disabled={deleting}>
          {t("action.cancel")}
        </Button>
        <Button
          variant="danger"
          size="md"
          onClick={handleDelete}
          disabled={deleting}
        >
          {deleting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}
          {t("action.delete")}
        </Button>
      </div>
    </Modal>
  );
}
