"use client";

import { type ReactNode, Fragment } from "react";

// ---------------------------------------------------------------------------
// Inline renderer: **bold**, *italic*, `code`
// ---------------------------------------------------------------------------
function renderInline(text: string): ReactNode {
  const PATTERN = /(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`)/g;
  const parts: ReactNode[] = [];
  let last = 0;
  let key = 0;
  let m: RegExpExecArray | null;

  while ((m = PATTERN.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    if (m[2] !== undefined) parts.push(<strong key={key++}>{m[2]}</strong>);
    else if (m[3] !== undefined) parts.push(<em key={key++}>{m[3]}</em>);
    else if (m[4] !== undefined) parts.push(<code key={key++}>{m[4]}</code>);
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts.length === 1 ? parts[0] : <Fragment>{parts}</Fragment>;
}

// ---------------------------------------------------------------------------
// Block-level parser
// ---------------------------------------------------------------------------
interface Block {
  type: "h1" | "h2" | "h3" | "ul" | "ol" | "pre" | "p";
  items?: string[];   // ul / ol
  text?: string;      // h1-h3, p
  code?: string;      // pre
}

function parseBlocks(src: string): Block[] {
  const lines = src.split("\n");
  const blocks: Block[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Blank line – skip
    if (!line.trim()) { i++; continue; }

    // Fenced code block
    if (line.startsWith("```")) {
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // closing ```
      blocks.push({ type: "pre", code: codeLines.join("\n") });
      continue;
    }

    // Headers
    if (line.startsWith("### ")) { blocks.push({ type: "h3", text: line.slice(4) }); i++; continue; }
    if (line.startsWith("## "))  { blocks.push({ type: "h2", text: line.slice(3) }); i++; continue; }
    if (line.startsWith("# "))   { blocks.push({ type: "h1", text: line.slice(2) }); i++; continue; }

    // Unordered list
    if (/^[-*+] /.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*+] /.test(lines[i])) {
        items.push(lines[i].slice(2));
        i++;
      }
      blocks.push({ type: "ul", items });
      continue;
    }

    // Ordered list
    if (/^\d+\. /.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\. /.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\. /, ""));
        i++;
      }
      blocks.push({ type: "ol", items });
      continue;
    }

    // Paragraph: collect consecutive non-block lines
    const paraLines: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !/^(#{1,3} |[-*+] |\d+\. |```)/.test(lines[i])
    ) {
      paraLines.push(lines[i]);
      i++;
    }
    if (paraLines.length) {
      blocks.push({ type: "p", text: paraLines.join(" ") });
    }
  }
  return blocks;
}

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------
export function Markdown({ children, className }: { children: string; className?: string }) {
  const blocks = parseBlocks(children ?? "");

  return (
    <div className={className}>
      {blocks.map((block, bi) => {
        switch (block.type) {
          case "h1": return <h1 key={bi}>{renderInline(block.text!)}</h1>;
          case "h2": return <h2 key={bi}>{renderInline(block.text!)}</h2>;
          case "h3": return <h3 key={bi}>{renderInline(block.text!)}</h3>;
          case "pre": return <pre key={bi}><code>{block.code}</code></pre>;
          case "ul":
            return (
              <ul key={bi}>
                {block.items!.map((it, ii) => <li key={ii}>{renderInline(it)}</li>)}
              </ul>
            );
          case "ol":
            return (
              <ol key={bi}>
                {block.items!.map((it, ii) => <li key={ii}>{renderInline(it)}</li>)}
              </ol>
            );
          default:
            return <p key={bi}>{renderInline(block.text!)}</p>;
        }
      })}
    </div>
  );
}
