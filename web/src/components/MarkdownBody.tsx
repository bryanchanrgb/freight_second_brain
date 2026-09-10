import { createContext, useContext, type ReactNode } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

const CITE_RE = /(\[\^?\d+\])/g;
const SEE_REPORT_RE = /(See the report(?: for sources and charts)?\.?)/i;

export const CiteContext = createContext<{
  onCite?: (n: number) => void;
  activeCite?: number | null;
}>({});

export default function MarkdownBody({
  children,
  onOpenReport,
}: {
  children: string;
  onOpenReport?: () => void;
}) {
  const { onCite, activeCite } = useContext(CiteContext);
  const mark = (nodes: ReactNode) => injectMarks(nodes, onCite, activeCite, onOpenReport);
  return (
    <div className="md-body">
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children: label }) => (
            <a href={href} target="_blank" rel="noreferrer">
              {label}
            </a>
          ),
          table: ({ children: rows }) => <table className="data">{rows}</table>,
          p: ({ children: nodes }) => <p>{mark(nodes)}</p>,
          li: ({ children: nodes }) => <li>{mark(nodes)}</li>,
          td: ({ children: nodes }) => <td>{mark(nodes)}</td>,
          th: ({ children: nodes }) => <th>{mark(nodes)}</th>,
          h1: ({ children: nodes }) => <h1>{mark(nodes)}</h1>,
          h2: ({ children: nodes }) => <h2>{mark(nodes)}</h2>,
          h3: ({ children: nodes }) => <h3>{mark(nodes)}</h3>,
        }}
      >
        {children}
      </Markdown>
    </div>
  );
}

function injectMarks(
  node: ReactNode,
  onCite?: (n: number) => void,
  activeCite?: number | null,
  onOpenReport?: () => void,
): ReactNode {
  if (!onCite && !onOpenReport) return node;
  if (typeof node === "string") return splitMarks(node, onCite, activeCite, onOpenReport);
  if (Array.isArray(node)) {
    return node.map((child, index) => (
      <span key={index}>{injectMarks(child, onCite, activeCite, onOpenReport)}</span>
    ));
  }
  return node;
}

function splitMarks(
  text: string,
  onCite?: (n: number) => void,
  activeCite?: number | null,
  onOpenReport?: () => void,
): ReactNode {
  const withCites = onCite ? splitCites(text, onCite, activeCite) : text;
  if (!onOpenReport) return withCites;
  if (typeof withCites === "string") return splitReportLink(withCites, onOpenReport);
  if (Array.isArray(withCites)) {
    return withCites.map((part, index) =>
      typeof part === "string" ? <span key={index}>{splitReportLink(part, onOpenReport)}</span> : part,
    );
  }
  return withCites;
}

function splitCites(text: string, onCite: (n: number) => void, activeCite?: number | null): ReactNode {
  const parts = text.split(CITE_RE);
  if (parts.length === 1) return text;
  return parts.map((part, index) => {
    const match = part.match(/^\[\^?(\d+)\]$/);
    if (!match) return part;
    const n = Number(match[1]);
    const active = activeCite === n;
    return (
      <button
        key={index}
        type="button"
        className={`cite-ref${active ? " active" : ""}`}
        data-cite={n}
        onClick={() => onCite(n)}
        title={`Open source ${n}`}
      >
        {n}
      </button>
    );
  });
}

function splitReportLink(text: string, onOpenReport: () => void): ReactNode {
  const parts = text.split(SEE_REPORT_RE);
  if (parts.length === 1) return text;
  return parts.map((part, index) => {
    if (!/^See the report(?: for sources and charts)?\.?$/i.test(part)) return part;
    return (
      <button
        key={index}
        type="button"
        className="report-link"
        onClick={onOpenReport}
      >
        {part}
      </button>
    );
  });
}
