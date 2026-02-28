"use client";

import { useState } from "react";
import { Send, X } from "lucide-react";

interface AdjustEditorProps {
  onSubmit: (feedback: string) => void;
  onCancel: () => void;
}

export default function AdjustEditor({ onSubmit, onCancel }: AdjustEditorProps) {
  const [feedback, setFeedback] = useState("");

  function handleSubmit() {
    const trimmed = feedback.trim();
    if (trimmed.length === 0) return;
    onSubmit(trimmed);
  }

  return (
    <div className="space-y-3">
      <div className="rounded-md border border-slate-700 bg-slate-800 p-3">
        <p className="mb-2 text-xs text-slate-500">
          Describe what should be adjusted. You can redirect research focus,
          request deeper investigation of specific topics, correct factual
          errors, or change the writing style.
        </p>
        <textarea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder="Enter your feedback or adjustment instructions..."
          rows={5}
          className="w-full resize-none rounded-md border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500/30"
          autoFocus
        />
      </div>
      <div className="flex justify-end gap-2">
        <button
          onClick={onCancel}
          className="flex items-center gap-1.5 rounded-md border border-slate-600 bg-slate-800 px-4 py-2 text-sm text-slate-400 transition-colors hover:bg-slate-700 hover:text-slate-300"
        >
          <X className="h-3.5 w-3.5" />
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={feedback.trim().length === 0}
          className="flex items-center gap-1.5 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Send className="h-3.5 w-3.5" />
          Submit
        </button>
      </div>
    </div>
  );
}
