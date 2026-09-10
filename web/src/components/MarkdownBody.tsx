import { createContext, useContext, type ReactNode } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

const CITE_RE = /(\[\^?\d+\])/g;

export const CiteContext = createContext<{
  onCite?: (n: number) => void;
  activeCite?: number | null;
}>({});

export default function MarkdownBody({ children }: { children: string }) {
  const { onCite, activeCite } = useContext(CiteContext);
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
          p: ({ children: nodes }) => <p>{injectCites(nodes, onCite, activeCite)}</p>,
          li: ({ children: nodes }) => <li>{injectCites(nodes, onCite, activeCite)}</li>,
          td: ({ children: nodes }) => <td>{injectCites(nodes, onCite, activeCite)}</td>,
          th: ({ children: nodes }) => <th>{injectCites(nodes, onCite, activeCite)}</th>,
          h1: ({ children: nodes }) => <h1>{injectCites(nodes, onCite, activeCite)}</h1>,
          h2: ({ children: nodes }) => <h2>{injectCites(nodes, onCite, activeCite)}</h2>,
          h3: ({ children: nodes }) => <h3>{injectCites(nodes, onCite, activeCite)}</h3>,
        }}
      >
        {children}
      </Markdown>
    </div>
  );
}

function injectCites(
  node: ReactNode,
  onCite?: (n: number) => void,
  activeCite?: number | null,
): ReactNode {
  if (!onCite) return node;
  if (typeof node === "string") return splitCites(node, onCite, activeCite);
  if (Array.isArray(node)) {
    return node.map((child, index) => (
      <span key={index}>{injectCites(child, onCite, activeCite)}</span>
    ));
  }
  return node;
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
