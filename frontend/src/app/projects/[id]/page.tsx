"use client";

import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  AlertTriangle,
  X,
  Trash2,
  Loader2,
  ChevronRight,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useLocale } from "@/contexts/LocaleContext";
import { ProjectSidebarProvider, useProjectSidebar } from "@/contexts/ProjectSidebarContext";
import { useProjectState } from "./_hooks/useProjectState";
import { PHASES } from "./_utils/formatters";
import { OverviewSection } from "./_components/OverviewSection";
import { BlackboardSection } from "./_components/BlackboardSection";
import { MessagesSection } from "./_components/MessagesSection";
import { KnowledgeSection } from "./_components/KnowledgeSection";
import { PaperSection } from "./_components/PaperSection";

export default function ProjectPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const state = useProjectState(projectId);
  const { t } = useLocale();

  if (state.loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-6 w-6 animate-spin text-aide-accent-blue" />
      </div>
    );
  }

  if (!state.project) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <p className="mb-4 text-aide-text-secondary">{t("empty.projectNotFound")}</p>
        <Link href="/">
          <Button variant="secondary" size="md">
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t("action.backToDashboard")}
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <ProjectSidebarProvider
      projectName={state.project.name}
      hasPaper={state.project.status === "completed" && !!state.paperContent}
    >
      <ProjectContent projectId={projectId} state={state} />
    </ProjectSidebarProvider>
  );
}

function ProjectContent({
  projectId,
  state,
}: {
  projectId: string;
  state: ReturnType<typeof useProjectState>;
}) {
  const router = useRouter();
  const { t } = useLocale();
  const sidebar = useProjectSidebar();
  const project = state.project!;
  const activeSection = sidebar?.activeSection ?? "overview";

  return (
    <div className="animate-fade-in">
      {/* Topic Drift Warning Toast */}
      {state.topicDriftWarning && (
        <div className="fixed bottom-6 right-6 z-50 flex max-w-sm items-start gap-3 rounded-xl border border-aide-accent-amber/50 bg-aide-bg-secondary px-4 py-3 shadow-xl animate-slide-up">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-aide-accent-amber" />
          <div>
            <p className="text-xs font-semibold text-aide-accent-amber">{t("section.topicDriftWarning")}</p>
            <p className="mt-0.5 text-xs text-aide-text-secondary">{state.topicDriftWarning}</p>
          </div>
          <button onClick={() => state.setTopicDriftWarning(null)} className="ml-auto text-aide-text-muted hover:text-aide-text-primary">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Top Bar */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <nav className="mb-1.5 flex items-center gap-1.5 text-sm">
            <Link
              href="/"
              className="text-aide-text-muted transition-colors hover:text-aide-text-primary"
            >
              {t("nav.projects")}
            </Link>
            <ChevronRight className="h-3.5 w-3.5 text-aide-text-muted" />
            <span className="font-medium text-aide-text-primary truncate max-w-[300px]">
              {project.name}
            </span>
          </nav>
          <p className="text-sm text-aide-text-secondary">
            {project.research_topic}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="phase">
            {t(PHASES.find((p) => p.key === project.phase)?.label ?? "phase.explore")}
          </Badge>
          <Badge variant={project.status === "running" ? "success" : project.status === "paused" ? "warning" : "default"}>
            {t((`status.${project.status}`) as import("@/lib/i18n").I18nKey)}
          </Badge>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => state.setShowDeleteConfirm(true)}
            className="text-aide-text-muted hover:bg-red-500/10 hover:text-red-400"
            title={t("action.deleteProject")}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Active Section */}
      {activeSection === "overview" && (
        <OverviewSection
          project={project}
          currentAgent={state.currentAgent}
          currentIteration={state.currentIteration}
          agentEvents={state.agentEvents}
          laneState={state.laneState}
          tokenUsage={state.tokenUsage}
          actionLoading={state.actionLoading}
          onToggleRunning={state.handleToggleRunning}
          blackboard={{
            artifacts: state.blackboard.artifacts as Record<string, unknown[]>,
            isLoading: state.blackboard.isLoading,
          }}
          wsStatus={state.ws.status}
        />
      )}

      {activeSection === "blackboard" && (
        <BlackboardSection
          artifacts={state.blackboard.artifacts as Record<string, unknown[]>}
          isLoading={state.blackboard.isLoading}
        />
      )}

      {activeSection === "messages" && (
        <MessagesSection
          messages={state.blackboard.messages}
          challenges={state.blackboard.challenges}
        />
      )}

      {activeSection === "knowledge" && (
        <KnowledgeSection
          projectId={projectId}
          citationGraph={state.citationGraph}
          onLoadCitationGraph={state.loadCitationGraph}
        />
      )}

      {activeSection === "paper" && (
        <PaperSection
          projectId={projectId}
          paperContent={state.paperContent}
          tokenUsage={state.tokenUsage}
          isCompleted={project.status === "completed"}
          onPaperContentChange={(content) => state.setPaperContent(content)}
        />
      )}

      {/* Delete Confirm Modal */}
      <Modal
        isOpen={state.showDeleteConfirm}
        onClose={() => state.setShowDeleteConfirm(false)}
        title={t("modal.deleteProject")}
        size="sm"
      >
        <p className="text-sm text-aide-text-secondary">
          {t("modal.deleteConfirm", { name: project.name })}
        </p>
        <p className="mt-1 text-xs text-aide-text-muted">
          {t("modal.deleteWarning")}
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" size="md" onClick={() => state.setShowDeleteConfirm(false)} disabled={state.deleting}>
            {t("action.cancel")}
          </Button>
          <Button
            variant="danger"
            size="md"
            onClick={async () => {
              const success = await state.handleDelete();
              if (success) router.push("/");
            }}
            disabled={state.deleting}
          >
            {state.deleting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}
            {t("action.delete")}
          </Button>
        </div>
      </Modal>

      {/* Checkpoint Modal */}
      <Modal
        isOpen={state.checkpoint !== null}
        onClose={() => {}}
        title={t("modal.checkpointReview")}
      >
        {state.checkpoint && (
          <div className="space-y-4">
            <Badge variant="phase">{state.checkpoint.phase}</Badge>
            <p className="text-sm text-aide-text-primary">
              {state.checkpoint.summary}
            </p>
            <div className="space-y-2">
              {state.checkpoint.options.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => state.handleCheckpointResponse(opt.value)}
                  disabled={state.checkpointLoading}
                  className="flex w-full items-center rounded-lg border border-aide-border bg-aide-bg-tertiary px-4 py-3 text-left text-sm text-aide-text-primary transition-colors hover:border-aide-accent-blue hover:bg-aide-accent-blue/10 disabled:opacity-50"
                >
                  {state.checkpointLoading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <ChevronRight className="mr-2 h-4 w-4 text-aide-text-muted" />
                  )}
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
