"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getExportedPaper,
  getProjectUsage,
  getCitationGraph,
  type ProjectTokenUsage,
  type CitationGraphData,
} from "@/lib/api";

export function usePaperState(projectId: string, projectStatus: string | undefined) {
  const [paperContent, setPaperContent] = useState<string | null>(null);
  const [tokenUsage, setTokenUsage] = useState<ProjectTokenUsage | null>(null);
  const [citationGraph, setCitationGraph] = useState<CitationGraphData | null>(null);

  // Load paper and usage for completed projects
  useEffect(() => {
    if (projectStatus !== "completed") return;
    getProjectUsage(projectId).then(setTokenUsage).catch(() => {});
    getExportedPaper(projectId)
      .then((data) => setPaperContent(data.content))
      .catch(() => {});
  }, [projectId, projectStatus]);

  const loadCitationGraph = useCallback(async () => {
    try {
      const data = await getCitationGraph(projectId);
      if (data.total_papers > 0) {
        setCitationGraph(data);
        return data;
      }
    } catch { /* no graph yet */ }
    return null;
  }, [projectId]);

  const loadTokenUsage = useCallback(async () => {
    try {
      const usage = await getProjectUsage(projectId);
      setTokenUsage(usage);
      return usage;
    } catch { return null; }
  }, [projectId]);

  return {
    paperContent, setPaperContent,
    tokenUsage, setTokenUsage,
    citationGraph,
    loadCitationGraph, loadTokenUsage,
  };
}
