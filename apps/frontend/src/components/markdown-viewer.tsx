import { useState, type ReactNode } from "react";
import { Check, Copy } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function renderInline(text: string): ReactNode[] {
  const tokens = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return tokens.map((tok, i) => {
    if (tok.startsWith("**") && tok.endsWith("**") && tok.length > 4) {
      return (
        <strong key={i} className="font-semibold text-slate-900">
          {tok.slice(2, -2)}
        </strong>
      );
    }
    if (tok.startsWith("`") && tok.endsWith("`") && tok.length > 2) {
      return (
        <code
          key={i}
          className="rounded bg-slate-200/80 px-1.5 py-0.5 font-mono text-[0.82em] text-[#B91C1C]"
        >
          {tok.slice(1, -1)}
        </code>
      );
    }
    return tok;
  });
}

interface Block {
  kind: "h1" | "h2" | "h3" | "code" | "ul" | "ol" | "p";
  lines: string[];
  lang?: string;
}

function parseBlocks(markdown: string): Block[] {
  const rawLines = markdown.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;

  while (i < rawLines.length) {
    const line = rawLines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      i += 1;
      continue;
    }

    if (trimmed.startsWith("```")) {
      const lang = trimmed.slice(3).trim();
      const codeLines: string[] = [];
      i += 1;
      while (i < rawLines.length && !rawLines[i].trim().startsWith("```")) {
        codeLines.push(rawLines[i]);
        i += 1;
      }
      i += 1;
      blocks.push({ kind: "code", lines: codeLines, lang });
      continue;
    }

    if (trimmed.startsWith("### ")) {
      blocks.push({ kind: "h3", lines: [trimmed.slice(4)] });
      i += 1;
      continue;
    }
    if (trimmed.startsWith("## ")) {
      blocks.push({ kind: "h2", lines: [trimmed.slice(3)] });
      i += 1;
      continue;
    }
    if (trimmed.startsWith("# ")) {
      blocks.push({ kind: "h1", lines: [trimmed.slice(2)] });
      i += 1;
      continue;
    }

    if (/^[-*]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < rawLines.length && /^[-*]\s+/.test(rawLines[i].trim())) {
        items.push(rawLines[i].trim().replace(/^[-*]\s+/, ""));
        i += 1;
      }
      blocks.push({ kind: "ul", lines: items });
      continue;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < rawLines.length && /^\d+\.\s+/.test(rawLines[i].trim())) {
        items.push(rawLines[i].trim().replace(/^\d+\.\s+/, ""));
        i += 1;
      }
      blocks.push({ kind: "ol", lines: items });
      continue;
    }

    const para: string[] = [];
    while (
      i < rawLines.length &&
      rawLines[i].trim() &&
      !rawLines[i].trim().startsWith("#") &&
      !rawLines[i].trim().startsWith("```") &&
      !/^[-*]\s+/.test(rawLines[i].trim()) &&
      !/^\d+\.\s+/.test(rawLines[i].trim())
    ) {
      para.push(rawLines[i]);
      i += 1;
    }
    blocks.push({ kind: "p", lines: para });
  }

  return blocks;
}

export function MarkdownViewer({ content, className }: { content: string; className?: string }) {
  const [copied, setCopied] = useState(false);
  const blocks = parseBlocks(content);

  async function onCopy() {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard may be unavailable in test environments
    }
  }

  return (
    <div
      className={cn(
        "relative max-h-96 overflow-auto rounded-xl border border-slate-200/90 bg-slate-50/90 p-4 text-sm text-slate-800",
        className,
      )}
    >
      <div className="sticky top-0 float-right ml-2 mb-1">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onCopy}
          className="h-7 bg-white/95 px-2 text-xs shadow-xs"
        >
          {copied ? <Check className="size-3 text-emerald-600" /> : <Copy className="size-3" />}
          <span>{copied ? "Đã chép" : "Sao chép"}</span>
        </Button>
      </div>

      <div className="space-y-2.5 leading-relaxed">
        {blocks.map((b, idx) => {
          if (b.kind === "h1") {
            return (
              <h3 key={idx} className="text-base font-bold text-slate-900">
                {renderInline(b.lines[0])}
              </h3>
            );
          }
          if (b.kind === "h2") {
            return (
              <h4 key={idx} className="text-sm font-bold text-slate-900">
                {renderInline(b.lines[0])}
              </h4>
            );
          }
          if (b.kind === "h3") {
            return (
              <h5 key={idx} className="text-xs font-bold tracking-wide text-[#E84142] uppercase">
                {renderInline(b.lines[0])}
              </h5>
            );
          }
          if (b.kind === "code") {
            return (
              <pre
                key={idx}
                className="overflow-x-auto rounded-lg bg-slate-900 p-3 font-mono text-xs text-slate-100"
              >
                {b.lines.join("\n")}
              </pre>
            );
          }
          if (b.kind === "ul") {
            return (
              <ul key={idx} className="list-disc space-y-1 pl-5">
                {b.lines.map((item, j) => (
                  <li key={j}>{renderInline(item)}</li>
                ))}
              </ul>
            );
          }
          if (b.kind === "ol") {
            return (
              <ol key={idx} className="list-decimal space-y-1 pl-5">
                {b.lines.map((item, j) => (
                  <li key={j}>{renderInline(item)}</li>
                ))}
              </ol>
            );
          }
          return (
            <p key={idx} className="whitespace-pre-wrap">
              {renderInline(b.lines.join("\n"))}
            </p>
          );
        })}
      </div>
    </div>
  );
}
