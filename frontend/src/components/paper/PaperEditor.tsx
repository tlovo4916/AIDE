"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import {
  Bold,
  Italic,
  Heading,
  List,
  Quote,
  Save,
  Check,
  Loader2,
  ChevronDown,
} from "lucide-react";
import PaperPreview from "./PaperPreview";

interface PaperEditorProps {
  content: string;
  onChange: (content: string) => void;
  onSave: (content: string) => void;
}

interface ToolbarAction {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  prefix: string;
  suffix: string;
}

const TOOLBAR_ACTIONS: ToolbarAction[] = [
  { icon: Bold, label: "Bold", prefix: "**", suffix: "**" },
  { icon: Italic, label: "Italic", prefix: "_", suffix: "_" },
  { icon: Heading, label: "Heading", prefix: "## ", suffix: "" },
  { icon: List, label: "List", prefix: "- ", suffix: "" },
  { icon: Quote, label: "Citation", prefix: "[^", suffix: "]" },
];

function extractSections(md: string): string[] {
  const matches = md.match(/^#{1,3}\s+.+$/gm);
  return matches ? matches.map((m) => m.replace(/^#+\s+/, "")) : [];
}

export default function PaperEditor({
  content,
  onChange,
  onSave,
}: PaperEditorProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">(
    "idle"
  );
  const [selectedSection, setSelectedSection] = useState<string | null>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout>>();

  const sections = extractSections(content);

  useEffect(() => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      setSaveState("saving");
      onSave(content);
      setTimeout(() => setSaveState("saved"), 300);
      setTimeout(() => setSaveState("idle"), 2000);
    }, 2000);

    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, [content, onSave]);

  const applyFormat = useCallback(
    (action: ToolbarAction) => {
      const textarea = textareaRef.current;
      if (!textarea) return;

      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const selected = content.slice(start, end);
      const replacement = `${action.prefix}${selected || "text"}${action.suffix}`;
      const newContent =
        content.slice(0, start) + replacement + content.slice(end);
      onChange(newContent);

      requestAnimationFrame(() => {
        textarea.focus();
        const newCursorPos = start + action.prefix.length;
        textarea.setSelectionRange(
          newCursorPos,
          newCursorPos + (selected || "text").length
        );
      });
    },
    [content, onChange]
  );

  function jumpToSection(section: string) {
    setSelectedSection(section);
    const textarea = textareaRef.current;
    if (!textarea) return;

    const pattern = new RegExp(`^#{1,3}\\s+${section.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`, "m");
    const match = content.match(pattern);
    if (match && match.index !== undefined) {
      textarea.focus();
      textarea.setSelectionRange(match.index, match.index);
      const linesBefore = content.slice(0, match.index).split("\n").length;
      const lineHeight = 20;
      textarea.scrollTop = (linesBefore - 1) * lineHeight;
    }
  }

  function handleManualSave() {
    setSaveState("saving");
    onSave(content);
    setTimeout(() => setSaveState("saved"), 300);
    setTimeout(() => setSaveState("idle"), 2000);
  }

  return (
    <div className="flex h-full flex-col">
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b border-slate-700 px-3 py-2">
        <div className="flex items-center gap-1">
          {TOOLBAR_ACTIONS.map((action) => {
            const Icon = action.icon;
            return (
              <button
                key={action.label}
                onClick={() => applyFormat(action)}
                title={action.label}
                className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-700 hover:text-slate-200"
              >
                <Icon className="h-4 w-4" />
              </button>
            );
          })}

          <div className="mx-2 h-5 w-px bg-slate-700" />

          {/* Section Selector */}
          {sections.length > 0 && (
            <div className="relative">
              <select
                value={selectedSection ?? ""}
                onChange={(e) => {
                  if (e.target.value) jumpToSection(e.target.value);
                }}
                className="appearance-none rounded-md border border-slate-600 bg-slate-800 py-1 pl-2 pr-7 text-xs text-slate-300 focus:border-blue-500 focus:outline-none"
              >
                <option value="">Jump to section...</option>
                {sections.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-1.5 top-1/2 h-3 w-3 -translate-y-1/2 text-slate-500" />
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Auto-save indicator */}
          <span className="flex items-center gap-1 text-xs text-slate-500">
            {saveState === "saving" && (
              <>
                <Loader2 className="h-3 w-3 animate-spin" />
                Saving...
              </>
            )}
            {saveState === "saved" && (
              <>
                <Check className="h-3 w-3 text-green-500" />
                Saved
              </>
            )}
          </span>
          <button
            onClick={handleManualSave}
            className="flex items-center gap-1.5 rounded-md border border-slate-600 bg-slate-800 px-3 py-1.5 text-xs text-slate-300 transition-colors hover:bg-slate-700"
          >
            <Save className="h-3.5 w-3.5" />
            Save
          </button>
        </div>
      </div>

      {/* Split View */}
      <div className="flex flex-1 overflow-hidden">
        {/* Editor */}
        <div className="flex-1 border-r border-slate-700">
          <textarea
            ref={textareaRef}
            value={content}
            onChange={(e) => onChange(e.target.value)}
            spellCheck={false}
            className="h-full w-full resize-none bg-slate-900 p-4 font-mono text-sm text-slate-300 placeholder:text-slate-600 focus:outline-none"
            placeholder="Start writing your paper in Markdown..."
          />
        </div>

        {/* Preview */}
        <div className="flex-1 overflow-hidden bg-slate-950">
          <PaperPreview content={content} title="Preview" />
        </div>
      </div>
    </div>
  );
}
