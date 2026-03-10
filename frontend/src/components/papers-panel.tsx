"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Upload,
  FileText,
  Trash2,
  Search,
  Loader2,
  X,
} from "lucide-react";
import {
  uploadPaper,
  listPapers,
  deletePaper,
  searchPapers,
} from "@/lib/api";

interface Paper {
  paper_id: string;
  filename: string;
  size_bytes: number;
}

interface SearchHit {
  chunk_id: string;
  content: string;
  source: string;
  score: number;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function PapersPanel({ projectId }: { projectId: string }) {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [uploading, setUploading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadPapers = useCallback(async () => {
    try {
      const list = await listPapers(projectId);
      setPapers(list);
    } catch {
      /* ignore */
    }
  }, [projectId]);

  useEffect(() => {
    loadPapers();
  }, [loadPapers]);

  const handleUpload = useCallback(
    async (files: FileList | File[]) => {
      setUploading(true);
      try {
        for (const file of Array.from(files)) {
          if (!file.name.toLowerCase().endsWith(".pdf")) continue;
          await uploadPaper(projectId, file);
        }
        await loadPapers();
      } catch (err) {
        console.error("Upload failed", err);
      } finally {
        setUploading(false);
      }
    },
    [projectId, loadPapers]
  );

  const handleDelete = useCallback(
    async (paperId: string) => {
      try {
        await deletePaper(projectId, paperId);
        setPapers((prev) => prev.filter((p) => p.paper_id !== paperId));
      } catch (err) {
        console.error("Delete failed", err);
      }
    },
    [projectId]
  );

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }
    setSearching(true);
    try {
      const results = await searchPapers(projectId, searchQuery);
      setSearchResults(results as unknown as SearchHit[]);
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }, [projectId, searchQuery]);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      if (e.dataTransfer.files.length > 0) {
        handleUpload(e.dataTransfer.files);
      }
    },
    [handleUpload]
  );

  return (
    <div className="space-y-3">
      <button
        onClick={() => setCollapsed((v) => !v)}
        className="flex w-full items-center gap-2 text-left"
      >
        <FileText className="h-4 w-4 text-aide-text-muted" />
        <h3 className="text-xs font-semibold uppercase tracking-wider text-aide-text-muted">
          Papers
        </h3>
        {papers.length > 0 && (
          <span className="ml-1 text-xs text-aide-text-muted">
            ({papers.length})
          </span>
        )}
        <span className="ml-auto text-xs text-aide-text-muted">
          {collapsed ? "+" : "−"}
        </span>
      </button>

      {!collapsed && (
        <>
          {/* Upload area */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`flex cursor-pointer flex-col items-center gap-1.5 rounded-md border border-dashed px-3 py-4 text-xs transition-colors ${
              dragOver
                ? "border-aide-accent-blue bg-aide-accent-blue/10 text-aide-accent-blue"
                : "border-aide-border text-aide-text-muted hover:border-aide-accent-blue/50 hover:text-aide-text-secondary"
            }`}
          >
            {uploading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Upload className="h-5 w-5" />
            )}
            <span>{uploading ? "上传中..." : "拖放 PDF 或点击上传"}</span>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              multiple
              className="hidden"
              onChange={(e) => {
                if (e.target.files) handleUpload(e.target.files);
                e.target.value = "";
              }}
            />
          </div>

          {/* Paper list */}
          {papers.length > 0 && (
            <div className="space-y-1">
              {papers.map((p) => (
                <div
                  key={p.paper_id}
                  className="flex items-center gap-2 rounded-md bg-aide-bg-tertiary px-2.5 py-1.5 text-xs"
                >
                  <FileText className="h-3.5 w-3.5 flex-shrink-0 text-aide-text-muted" />
                  <span className="flex-1 truncate text-aide-text-secondary">
                    {p.filename}
                  </span>
                  <span className="flex-shrink-0 text-aide-text-muted">
                    {formatSize(p.size_bytes)}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(p.paper_id);
                    }}
                    className="flex-shrink-0 text-aide-text-muted hover:text-red-400 transition-colors"
                    title="删除"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Search */}
          <div className="flex items-center gap-1.5">
            <div className="relative flex-1">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder="搜索论文内容..."
                className="w-full rounded-md border border-aide-border bg-aide-bg-tertiary px-2.5 py-1.5 pr-7 text-xs text-aide-text-primary placeholder:text-aide-text-muted focus:border-aide-accent-blue focus:outline-none"
              />
              {searchQuery && (
                <button
                  onClick={() => {
                    setSearchQuery("");
                    setSearchResults(null);
                  }}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 text-aide-text-muted hover:text-aide-text-primary"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>
            <button
              onClick={handleSearch}
              disabled={searching || !searchQuery.trim()}
              className="rounded-md border border-aide-border bg-aide-bg-tertiary p-1.5 text-aide-text-muted hover:text-aide-accent-blue transition-colors disabled:opacity-50"
            >
              {searching ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Search className="h-3.5 w-3.5" />
              )}
            </button>
          </div>

          {/* Search results */}
          {searchResults !== null && (
            <div className="space-y-1">
              {searchResults.length === 0 ? (
                <p className="text-xs text-aide-text-muted px-1">无搜索结果</p>
              ) : (
                searchResults.slice(0, 5).map((r) => (
                  <div
                    key={r.chunk_id}
                    className="rounded-md bg-aide-bg-tertiary px-2.5 py-2 text-xs"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-aide-text-muted">{r.source}</span>
                      <span className="text-aide-text-muted">
                        {r.score.toFixed(2)}
                      </span>
                    </div>
                    <p className="text-aide-text-secondary line-clamp-3">
                      {r.content}
                    </p>
                  </div>
                ))
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
