"use client";

import { useState } from "react";
import {
  Search,
  Loader2,
  FileText,
  ToggleLeft,
  ToggleRight,
} from "lucide-react";

type SearchMode = "hybrid" | "vector" | "bm25";

interface SearchResult {
  id: string;
  score: number;
  source_document: string;
  chunk_preview: string;
  highlights: string[];
}

interface SearchTesterProps {
  projectId: string;
}

const MODE_LABELS: Record<SearchMode, string> = {
  hybrid: "Hybrid",
  vector: "Vector",
  bm25: "BM25",
};

function ScoreBar({ score }: { score: number }) {
  const pct = Math.min(score * 100, 100);
  const color =
    score >= 0.8
      ? "bg-green-500"
      : score >= 0.5
        ? "bg-blue-500"
        : "bg-amber-400";

  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-700">
        <div
          className={`h-full rounded-full ${color} transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs tabular-nums text-slate-500">
        {score.toFixed(3)}
      </span>
    </div>
  );
}

function HighlightedText({ text, highlights }: { text: string; highlights: string[] }) {
  if (highlights.length === 0) {
    return <span>{text}</span>;
  }

  const pattern = new RegExp(
    `(${highlights.map((h) => h.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`,
    "gi"
  );

  const parts = text.split(pattern);

  return (
    <span>
      {parts.map((part, i) => {
        const isHighlight = highlights.some(
          (h) => h.toLowerCase() === part.toLowerCase()
        );
        return isHighlight ? (
          <mark
            key={i}
            className="rounded bg-blue-500/20 px-0.5 text-blue-300"
          >
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        );
      })}
    </span>
  );
}

export default function SearchTester({ projectId }: SearchTesterProps) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  async function handleSearch() {
    if (!query.trim()) return;
    setIsSearching(true);

    try {
      const res = await fetch(
        `/api/knowledge/${projectId}/search?q=${encodeURIComponent(query)}&mode=${mode}`
      );
      if (res.ok) {
        const data = await res.json();
        setResults(data.results ?? []);
      }
    } catch {
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSearch();
    }
  }

  return (
    <div className="flex h-full flex-col">
      {/* Search Input */}
      <div className="border-b border-slate-700 p-4">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Enter search query..."
              className="w-full rounded-md border border-slate-600 bg-slate-800 py-2 pl-10 pr-3 text-sm text-slate-200 placeholder:text-slate-600 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500/30"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={isSearching || !query.trim()}
            className="flex items-center gap-1.5 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {isSearching ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Search className="h-4 w-4" />
            )}
            Search
          </button>
        </div>

        {/* Mode Toggle */}
        <div className="mt-3 flex items-center gap-1">
          {(Object.keys(MODE_LABELS) as SearchMode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs transition-colors ${
                mode === m
                  ? "bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/30"
                  : "text-slate-500 hover:bg-slate-800 hover:text-slate-300"
              }`}
            >
              {mode === m ? (
                <ToggleRight className="h-3.5 w-3.5" />
              ) : (
                <ToggleLeft className="h-3.5 w-3.5" />
              )}
              {MODE_LABELS[m]}
            </button>
          ))}
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {results.length === 0 && !isSearching && query && (
          <p className="py-8 text-center text-sm text-slate-600">
            No results found
          </p>
        )}

        {results.length === 0 && !query && (
          <p className="py-8 text-center text-sm text-slate-600">
            Enter a query to search the knowledge base
          </p>
        )}

        {results.map((result) => (
          <div
            key={result.id}
            className="rounded-lg border border-slate-700 bg-slate-800 p-3"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <FileText className="h-3.5 w-3.5 text-slate-500" />
                <span className="text-xs text-slate-400">
                  {result.source_document}
                </span>
              </div>
              <ScoreBar score={result.score} />
            </div>
            <p className="text-sm leading-relaxed text-slate-300">
              <HighlightedText
                text={result.chunk_preview}
                highlights={result.highlights}
              />
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
