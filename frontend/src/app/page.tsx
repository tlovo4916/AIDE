"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Plus, FlaskConical, Calendar, Loader2, X, Trash2, AlertTriangle } from "lucide-react";
import { listProjects, createProject, deleteProject } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Project {
  id: string;
  name: string;
  research_topic: string;
  phase: string;
  status: string;
  created_at: string;
}

const PHASE_LABELS: Record<string, string> = {
  direction: "Direction",
  hypothesis: "Hypothesis",
  evidence: "Evidence",
  synthesis: "Synthesis",
};

const STATUS_VARIANT: Record<string, "success" | "warning" | "default"> = {
  running: "success",
  paused: "warning",
  completed: "default",
  failed: "default",
};

export default function DashboardPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [name, setName] = useState("");
  const [topic, setTopic] = useState("");
  const [creating, setCreating] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch(() => setProjects([]))
      .finally(() => setLoading(false));
  }, []);

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteProject(deleteTarget.id);
      setProjects((prev) => prev.filter((p) => p.id !== deleteTarget.id));
      setDeleteTarget(null);
    } finally {
      setDeleting(false);
    }
  }

  async function handleCreate() {
    if (!name.trim() || !topic.trim()) return;
    setCreating(true);
    try {
      const { id } = await createProject({ name: name.trim(), research_topic: topic.trim() });
      router.push(`/projects/${id}`);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="animate-fade-in">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-aide-text-primary">
            Research Projects
          </h1>
          <p className="mt-1 text-sm text-aide-text-secondary">
            Manage and monitor your AI-assisted research workflows
          </p>
        </div>
        <Button variant="primary" size="md" onClick={() => setShowModal(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Project
        </Button>
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-lg border border-aide-border bg-aide-surface p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-aide-text-primary">New Research Project</h2>
              <button onClick={() => setShowModal(false)}><X className="h-4 w-4 text-aide-text-muted" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-sm text-aide-text-secondary">Project Name</label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Protein Folding Study" />
              </div>
              <div>
                <label className="mb-1 block text-sm text-aide-text-secondary">Research Topic</label>
                <Input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Describe what you want to research..." />
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="ghost" size="md" onClick={() => setShowModal(false)}>Cancel</Button>
              <Button variant="primary" size="md" onClick={handleCreate} disabled={creating || !name.trim() || !topic.trim()}>
                {creating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
                Create
              </Button>
            </div>
          </div>
        </div>
      )}

      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-sm rounded-lg border border-aide-border bg-aide-surface p-6 shadow-xl">
            <div className="mb-4 flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-aide-accent-amber" />
              <div>
                <h2 className="text-base font-semibold text-aide-text-primary">删除项目</h2>
                <p className="mt-1 text-sm text-aide-text-secondary">
                  确认删除 <span className="font-medium text-aide-text-primary">{deleteTarget.name}</span>？
                </p>
                <p className="mt-1 text-xs text-aide-text-muted">
                  此操作不可撤销，将同时删除所有研究 artifacts 和文件数据。
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="md" onClick={() => setDeleteTarget(null)} disabled={deleting}>
                取消
              </Button>
              <Button
                variant="primary"
                size="md"
                onClick={handleDelete}
                disabled={deleting}
                className="bg-red-600 hover:bg-red-700 focus:ring-red-500"
              >
                {deleting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}
                确认删除
              </Button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-6 w-6 animate-spin text-aide-accent-blue" />
        </div>
      ) : projects.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-aide-border py-24">
          <FlaskConical className="mb-4 h-10 w-10 text-aide-text-muted" />
          <h2 className="mb-1 text-lg font-medium text-aide-text-primary">
            No projects yet
          </h2>
          <p className="mb-6 text-sm text-aide-text-secondary">
            Create your first research project to get started
          </p>
          <Button variant="primary" size="md" onClick={() => setShowModal(true)}>
            <Plus className="mr-2 h-4 w-4" />
            New Project
          </Button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <div key={project.id} className="relative group">
              <Link href={`/projects/${project.id}`}>
                <Card className="cursor-pointer transition-colors hover:border-aide-accent-blue/40">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <CardTitle className="text-base pr-7">{project.name}</CardTitle>
                      <Badge variant={STATUS_VARIANT[project.status] ?? "default"}>
                        {project.status}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="mb-4 line-clamp-2 text-sm text-aide-text-secondary">
                      {project.research_topic}
                    </p>
                    <div className="flex items-center justify-between">
                      <Badge variant="phase">
                        {PHASE_LABELS[project.phase] ?? project.phase}
                      </Badge>
                      <span className="flex items-center gap-1 text-xs text-aide-text-muted">
                        <Calendar className="h-3 w-3" />
                        {new Date(
                          project.created_at.endsWith("Z") ? project.created_at : project.created_at + "Z"
                        ).toLocaleDateString()}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              </Link>
              <button
                onClick={(e) => { e.preventDefault(); setDeleteTarget(project); }}
                className="absolute right-3 top-3 rounded-md p-1 text-aide-text-muted opacity-0 transition-opacity group-hover:opacity-100 hover:bg-red-500/10 hover:text-red-400"
                title="删除项目"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
