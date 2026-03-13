"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Plus, FlaskConical, Calendar, Clock, Loader2, Trash2 } from "lucide-react";
import { listProjects, createProject, deleteProject } from "@/lib/api";
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

function CreateProjectModal({
  isOpen,
  onClose,
  onCreate,
}: {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (id: string) => void;
}) {
  const { t } = useLocale();
  const [name, setName] = useState("");
  const [topic, setTopic] = useState("");
  const [concurrency, setConcurrency] = useState(1);
  const [creating, setCreating] = useState(false);

  async function handleCreate() {
    if (!name.trim() || !topic.trim()) return;
    setCreating(true);
    try {
      const { id } = await createProject({ name: name.trim(), research_topic: topic.trim(), concurrency });
      onCreate(id);
    } finally {
      setCreating(false);
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={t("modal.newProject")} size="md">
      <div className="space-y-3">
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
