import type { ReactNode } from "react";

type MarkdownReportProps = {
  markdown: string;
};

type Token =
  | { kind: "heading"; level: 1 | 2 | 3; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "bullet"; text: string }
  | { kind: "blockquote"; text: string }
  | { kind: "code"; text: string }
  | { kind: "divider" };

function MarkdownReport({ markdown }: MarkdownReportProps) {
  const tokens = parseMarkdown(markdown);

  return (
    <article className="rounded-3xl border border-white/10 bg-slate-950/50 p-5 shadow-inner shadow-slate-950/30">
      <div className="space-y-4">
        {tokens.map((token, index) => {
          switch (token.kind) {
            case "heading":
              return (
                <Heading key={index} level={token.level}>
                  {token.text}
                </Heading>
              );
            case "paragraph":
              return (
                <p key={index} className="text-sm leading-7 text-slate-200">
                  {renderInline(token.text)}
                </p>
              );
            case "bullet":
              return (
                <li key={index} className="ml-5 list-disc text-sm leading-7 text-slate-200">
                  {renderInline(token.text)}
                </li>
              );
            case "blockquote":
              return (
                <blockquote key={index} className="border-l-2 border-cyan-300/60 pl-4 text-sm leading-7 text-cyan-100/90">
                  {renderInline(token.text)}
                </blockquote>
              );
            case "code":
              return (
                <pre key={index} className="overflow-x-auto rounded-2xl border border-white/10 bg-slate-900/80 p-4 text-sm leading-7 text-cyan-100">
                  <code>{token.text}</code>
                </pre>
              );
            case "divider":
              return <hr key={index} className="border-white/10" />;
            default:
              return null;
          }
        })}
      </div>
    </article>
  );
}

function Heading({ level, children }: { level: 1 | 2 | 3; children: ReactNode }) {
  const className =
    level === 1
      ? "text-3xl font-semibold tracking-tight text-white"
      : level === 2
        ? "text-2xl font-semibold tracking-tight text-white"
        : "text-lg font-semibold tracking-tight text-white";

  if (level === 1) return <h1 className={className}>{children}</h1>;
  if (level === 2) return <h2 className={className}>{children}</h2>;
  return <h3 className={className}>{children}</h3>;
}

function renderInline(text: string) {
  return text
    .split(/(`[^`]+`)/g)
    .map((part, index) => {
      if (part.startsWith("`") && part.endsWith("`")) {
        return (
          <code key={index} className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[0.92em] text-cyan-100">
            {part.slice(1, -1)}
          </code>
        );
      }

      const segments = part.split(/(\*\*[^*]+\*\*)/g);
      return segments.map((segment, segmentIndex) => {
        if (segment.startsWith("**") && segment.endsWith("**")) {
          return (
            <strong key={`${index}-${segmentIndex}`} className="font-semibold text-white">
              {segment.slice(2, -2)}
            </strong>
          );
        }

        return <span key={`${index}-${segmentIndex}`}>{segment}</span>;
      });
    });
}

function parseMarkdown(markdown: string): Token[] {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const tokens: Token[] = [];
  let codeBuffer: string[] = [];
  let inCode = false;

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();

    if (line.startsWith("```") ) {
      if (inCode) {
        tokens.push({ kind: "code", text: codeBuffer.join("\n") });
        codeBuffer = [];
      }
      inCode = !inCode;
      continue;
    }

    if (inCode) {
      codeBuffer.push(rawLine);
      continue;
    }

    if (!line.trim()) {
      tokens.push({ kind: "divider" });
      continue;
    }

    if (line.startsWith("### ")) {
      tokens.push({ kind: "heading", level: 3, text: line.slice(4).trim() });
      continue;
    }

    if (line.startsWith("## ")) {
      tokens.push({ kind: "heading", level: 2, text: line.slice(3).trim() });
      continue;
    }

    if (line.startsWith("# ")) {
      tokens.push({ kind: "heading", level: 1, text: line.slice(2).trim() });
      continue;
    }

    if (line.startsWith("> ")) {
      tokens.push({ kind: "blockquote", text: line.slice(2).trim() });
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      tokens.push({ kind: "bullet", text: line.replace(/^[-*]\s+/, "") });
      continue;
    }

    tokens.push({ kind: "paragraph", text: line });
  }

  if (inCode && codeBuffer.length) {
    tokens.push({ kind: "code", text: codeBuffer.join("\n") });
  }

  return tokens;
}

export default MarkdownReport;
