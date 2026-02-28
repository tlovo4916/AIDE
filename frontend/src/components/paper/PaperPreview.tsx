"use client";

import { useState, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { Download, FileText, List } from "lucide-react";

interface PaperPreviewProps {
  content: string;
  title: string;
}

interface Section {
  id: string;
  title: string;
  level: number;
}

function extractSections(markdown: string): Section[] {
  const sections: Section[] = [];
  const lines = markdown.split("\n");
  for (const line of lines) {
    const match = line.match(/^(#{1,3})\s+(.+)$/);
    if (match) {
      const level = match[1].length;
      const title = match[2].trim();
      const id = title
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/(^-|-$)/g, "");
      sections.push({ id, title, level });
    }
  }
  return sections;
}

function downloadMarkdown(content: string, title: string) {
  const blob = new Blob([content], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${title.replace(/[^a-zA-Z0-9]/g, "_")}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function PaperPreview({ content, title }: PaperPreviewProps) {
  const [showSidebar, setShowSidebar] = useState(true);
  const sections = useMemo(() => extractSections(content), [content]);

  function scrollToSection(id: string) {
    const el = document.getElementById(id);
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <div className="flex h-full">
      {/* Section Navigation Sidebar */}
      {showSidebar && sections.length > 0 && (
        <nav className="w-56 shrink-0 overflow-y-auto border-r border-slate-700 p-3">
          <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
            <List className="h-3.5 w-3.5" />
            Sections
          </h3>
          <ul className="space-y-0.5">
            {sections.map((section) => (
              <li key={section.id}>
                <button
                  onClick={() => scrollToSection(section.id)}
                  className={`w-full truncate rounded px-2 py-1 text-left text-xs transition-colors hover:bg-slate-800 hover:text-slate-200 ${
                    section.level === 1
                      ? "font-medium text-slate-300"
                      : section.level === 2
                        ? "pl-4 text-slate-400"
                        : "pl-6 text-slate-500"
                  }`}
                >
                  {section.title}
                </button>
              </li>
            ))}
          </ul>
        </nav>
      )}

      {/* Main Content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="flex items-center justify-between border-b border-slate-700 px-4 py-2.5">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSidebar(!showSidebar)}
              className={`rounded-md p-1.5 text-sm transition-colors ${
                showSidebar
                  ? "bg-slate-700 text-slate-200"
                  : "text-slate-500 hover:bg-slate-800 hover:text-slate-300"
              }`}
              title="Toggle section sidebar"
            >
              <List className="h-4 w-4" />
            </button>
            <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-200">
              <FileText className="h-4 w-4 text-blue-400" />
              {title}
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => downloadMarkdown(content, title)}
              className="flex items-center gap-1.5 rounded-md border border-slate-600 bg-slate-800 px-3 py-1.5 text-xs text-slate-300 transition-colors hover:bg-slate-700"
            >
              <Download className="h-3.5 w-3.5" />
              Download MD
            </button>
            <button
              disabled
              className="flex items-center gap-1.5 rounded-md border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs text-slate-600 cursor-not-allowed"
              title="PDF export coming soon"
            >
              <Download className="h-3.5 w-3.5" />
              PDF
            </button>
          </div>
        </div>

        {/* Markdown Render */}
        <div className="flex-1 overflow-y-auto p-6">
          <article className="mx-auto max-w-3xl">
            <ReactMarkdown
              remarkPlugins={[remarkMath]}
              rehypePlugins={[rehypeKatex]}
              components={{
                h1: ({ children, ...props }) => (
                  <h1
                    id={String(children)
                      .toLowerCase()
                      .replace(/[^a-z0-9]+/g, "-")
                      .replace(/(^-|-$)/g, "")}
                    className="mt-8 mb-4 text-2xl font-bold text-slate-100 border-b border-slate-700 pb-2"
                    {...props}
                  >
                    {children}
                  </h1>
                ),
                h2: ({ children, ...props }) => (
                  <h2
                    id={String(children)
                      .toLowerCase()
                      .replace(/[^a-z0-9]+/g, "-")
                      .replace(/(^-|-$)/g, "")}
                    className="mt-6 mb-3 text-xl font-semibold text-slate-200"
                    {...props}
                  >
                    {children}
                  </h2>
                ),
                h3: ({ children, ...props }) => (
                  <h3
                    id={String(children)
                      .toLowerCase()
                      .replace(/[^a-z0-9]+/g, "-")
                      .replace(/(^-|-$)/g, "")}
                    className="mt-4 mb-2 text-lg font-medium text-slate-300"
                    {...props}
                  >
                    {children}
                  </h3>
                ),
                p: ({ children }) => (
                  <p className="mb-4 leading-relaxed text-slate-300">
                    {children}
                  </p>
                ),
                ul: ({ children }) => (
                  <ul className="mb-4 ml-6 list-disc space-y-1 text-slate-300">
                    {children}
                  </ul>
                ),
                ol: ({ children }) => (
                  <ol className="mb-4 ml-6 list-decimal space-y-1 text-slate-300">
                    {children}
                  </ol>
                ),
                li: ({ children }) => (
                  <li className="text-slate-300">{children}</li>
                ),
                blockquote: ({ children }) => (
                  <blockquote className="mb-4 border-l-4 border-blue-500/50 pl-4 text-slate-400 italic">
                    {children}
                  </blockquote>
                ),
                code: ({ className, children, ...props }) => {
                  const isInline = !className;
                  if (isInline) {
                    return (
                      <code className="rounded bg-slate-800 px-1.5 py-0.5 text-sm text-blue-300 font-mono">
                        {children}
                      </code>
                    );
                  }
                  return (
                    <code
                      className="block overflow-x-auto rounded-md bg-slate-900 p-4 text-sm text-slate-300 font-mono"
                      {...props}
                    >
                      {children}
                    </code>
                  );
                },
                pre: ({ children }) => (
                  <pre className="mb-4">{children}</pre>
                ),
                a: ({ href, children }) => (
                  <a
                    href={href}
                    className="text-blue-400 underline decoration-blue-400/30 hover:decoration-blue-400 transition-colors"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {children}
                  </a>
                ),
                table: ({ children }) => (
                  <div className="mb-4 overflow-x-auto">
                    <table className="w-full border-collapse text-sm">
                      {children}
                    </table>
                  </div>
                ),
                th: ({ children }) => (
                  <th className="border border-slate-700 bg-slate-800 px-3 py-2 text-left text-slate-300 font-medium">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="border border-slate-700 px-3 py-2 text-slate-400">
                    {children}
                  </td>
                ),
              }}
            >
              {content}
            </ReactMarkdown>
          </article>
        </div>
      </div>
    </div>
  );
}
