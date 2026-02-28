"use client";

import { useState, useRef, useCallback } from "react";
import {
  Upload,
  FileText,
  Trash2,
  X,
  File,
} from "lucide-react";

interface Paper {
  id: string;
  title: string;
  pages: number;
  chunks: number;
  filename: string;
}

interface PDFUploaderProps {
  projectId: string;
  papers: Paper[];
  onUpload: (projectId: string, file: File) => Promise<void>;
  onDelete: (projectId: string, paperId: string) => void;
}

export default function PDFUploader({
  projectId,
  papers,
  onUpload,
  onDelete,
}: PDFUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadFileName, setUploadFileName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    async (file: File) => {
      if (file.type !== "application/pdf") return;
      setUploadFileName(file.name);
      setUploadProgress(0);

      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => {
          if (prev === null || prev >= 90) return prev;
          return prev + Math.random() * 15;
        });
      }, 200);

      try {
        await onUpload(projectId, file);
        setUploadProgress(100);
        setTimeout(() => {
          setUploadProgress(null);
          setUploadFileName(null);
        }, 1000);
      } catch {
        setUploadProgress(null);
        setUploadFileName(null);
      } finally {
        clearInterval(progressInterval);
      }
    },
    [onUpload, projectId]
  );

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(true);
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(false);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  return (
    <div className="space-y-4">
      {/* Drop Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors ${
          isDragging
            ? "border-blue-500 bg-blue-500/5"
            : "border-slate-700 bg-slate-800/50 hover:border-slate-600"
        }`}
      >
        <Upload
          className={`mb-3 h-8 w-8 ${
            isDragging ? "text-blue-400" : "text-slate-500"
          }`}
        />
        <p className="text-sm text-slate-300">
          Drop PDF files here, or{" "}
          <button
            onClick={() => fileInputRef.current?.click()}
            className="text-blue-400 underline decoration-blue-400/30 hover:decoration-blue-400"
          >
            browse
          </button>
        </p>
        <p className="mt-1 text-xs text-slate-600">PDF files only</p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          onChange={handleInputChange}
          className="hidden"
        />
      </div>

      {/* Upload Progress */}
      {uploadProgress !== null && uploadFileName && (
        <div className="rounded-md border border-slate-700 bg-slate-800 p-3">
          <div className="flex items-center gap-2 mb-2">
            <File className="h-4 w-4 text-blue-400" />
            <span className="text-sm text-slate-300 truncate flex-1">
              {uploadFileName}
            </span>
            <span className="text-xs tabular-nums text-slate-500">
              {Math.round(uploadProgress)}%
            </span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-700">
            <div
              className="h-full rounded-full bg-blue-500 transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* Paper List */}
      {papers.length > 0 && (
        <div className="space-y-1.5">
          <h3 className="flex items-center gap-2 px-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
            <FileText className="h-3.5 w-3.5" />
            Uploaded Papers ({papers.length})
          </h3>
          <div className="space-y-1">
            {papers.map((paper) => (
              <div
                key={paper.id}
                className="group flex items-center gap-3 rounded-md border border-slate-700 bg-slate-800 px-3 py-2.5"
              >
                <FileText className="h-4 w-4 shrink-0 text-slate-500" />
                <div className="flex-1 min-w-0">
                  <p className="truncate text-sm text-slate-300">
                    {paper.title}
                  </p>
                  <div className="flex gap-3 text-xs text-slate-500">
                    <span>{paper.pages} pages</span>
                    <span>{paper.chunks} chunks</span>
                  </div>
                </div>
                <button
                  onClick={() => onDelete(projectId, paper.id)}
                  className="rounded p-1 text-slate-600 opacity-0 transition-all hover:bg-red-500/10 hover:text-red-400 group-hover:opacity-100"
                  title="Remove paper"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {papers.length === 0 && uploadProgress === null && (
        <p className="py-4 text-center text-sm text-slate-600">
          No papers uploaded yet
        </p>
      )}
    </div>
  );
}
