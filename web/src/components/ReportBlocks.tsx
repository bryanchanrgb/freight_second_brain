import { useState } from "react";
import type { Artifact, ReportBlock } from "../types";
import MarkdownBody from "./MarkdownBody";
import PrintsChart from "./PrintsChart";
import PrintsTable from "./PrintsTable";

export default function ReportBlocks({ blocks }: { blocks: ReportBlock[] }) {
  if (!blocks.length) return null;
  return (
    <div className="report-blocks">
      {blocks.map((block, index) => (
        <ReportBlockView key={`${block.type}-${index}`} block={block} index={index} />
      ))}
    </div>
  );
}

function ReportBlockView({ block, index }: { block: ReportBlock; index: number }) {
  const kind = String(block.type || "");
  if (kind === "divider") return <hr className="report-divider" />;
  if (kind === "heading") {
    const level = Math.min(3, Math.max(1, Number(block.level) || 2));
    const Tag = (`h${level}` as "h1" | "h2" | "h3");
    return <Tag className={`report-h report-h${level}`}>{String(block.text || "")}</Tag>;
  }
  if (kind === "markdown") {
    return <MarkdownBody>{String(block.text || "")}</MarkdownBody>;
  }
  if (kind === "callout") {
    return (
      <aside className={`callout tone-${String(block.tone || "info")}`}>
        {block.title ? <div className="callout-title">{String(block.title)}</div> : null}
        <MarkdownBody>{String(block.text || "")}</MarkdownBody>
      </aside>
    );
  }
  if (kind === "quote") {
    return (
      <blockquote className="report-quote">
        <MarkdownBody>{String(block.text || "")}</MarkdownBody>
        {block.attribution ? <cite>{String(block.attribution)}</cite> : null}
      </blockquote>
    );
  }
  if (kind === "kpis") {
    const items = Array.isArray(block.items) ? (block.items as Record<string, unknown>[]) : [];
    return (
      <div className="kpi-row">
        {items.map((item, idx) => (
          <div key={idx} className="kpi">
            <div className="kpi-label">{String(item.label ?? "")}</div>
            <div className="kpi-value">{String(item.value ?? "")}</div>
            {item.caption ? <div className="kpi-caption">{String(item.caption)}</div> : null}
          </div>
        ))}
      </div>
    );
  }
  if (kind === "table") {
    const artifact = blockAsArtifact(`table-${index}`, "table", block);
    return <PrintsTable artifact={artifact} />;
  }
  if (kind === "chart") {
    const artifact = blockAsArtifact(`chart-${index}`, "chart", block);
    return <PrintsChart artifact={artifact} />;
  }
  if (kind === "citations") {
    const items = Array.isArray(block.items) ? (block.items as Record<string, unknown>[]) : [];
    return (
      <section className="citations">
        <h3 className="report-h report-h3">Sources</h3>
        <ol>
          {items.map((item, idx) => {
            const title = String(item.title || item.url || "Source");
            const url = String(item.url || "");
            const meta = [item.publisher, item.as_of, item.note].filter(Boolean).map(String).join(" · ");
            return (
              <li key={idx}>
                {url ? (
                  <a href={url} target="_blank" rel="noreferrer">
                    {title}
                  </a>
                ) : (
                  <span>{title}</span>
                )}
                {meta ? <div className="cite-meta">{meta}</div> : null}
              </li>
            );
          })}
        </ol>
      </section>
    );
  }
  if (kind === "expand") {
    return <ExpandBlock block={block} />;
  }
  if (kind === "diagram") {
    return <DiagramBlock block={block} />;
  }
  if (block.text) {
    return <MarkdownBody>{String(block.text)}</MarkdownBody>;
  }
  return null;
}

function ExpandBlock({ block }: { block: ReportBlock }) {
  const [open, setOpen] = useState(false);
  const nested = Array.isArray(block.blocks) ? (block.blocks as ReportBlock[]) : [];
  return (
    <div className="expand-block">
      <button type="button" className="expand" onClick={() => setOpen((value) => !value)}>
        {open ? "Hide" : "Show"} {String(block.title || "Details")}
      </button>
      {open ? <ReportBlocks blocks={nested} /> : null}
    </div>
  );
}

function DiagramBlock({ block }: { block: ReportBlock }) {
  const nodes = Array.isArray(block.nodes) ? (block.nodes as Record<string, unknown>[]) : [];
  const edges = Array.isArray(block.edges) ? (block.edges as Record<string, unknown>[]) : [];
  const labels = new Map(nodes.map((node) => [String(node.id), String(node.label || node.id)]));
  return (
    <section className="diagram">
      {block.title ? <h3 className="report-h report-h3">{String(block.title)}</h3> : null}
      <div className="diagram-flow">
        {nodes.map((node, idx) => (
          <div key={String(node.id || idx)} className="diagram-node">
            {String(node.label || node.id)}
          </div>
        ))}
      </div>
      {edges.length ? (
        <ul className="diagram-edges">
          {edges.map((edge, idx) => (
            <li key={idx}>
              <span>{labels.get(String(edge.from)) || String(edge.from)}</span>
              <span className="diagram-arrow">{edge.label ? ` — ${String(edge.label)} → ` : " → "}</span>
              <span>{labels.get(String(edge.to)) || String(edge.to)}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function blockAsArtifact(id: string, kind: "table" | "chart", block: ReportBlock): Artifact {
  return {
    id,
    kind,
    status: "active",
    title: String(block.title || ""),
    subtitle: block.subtitle ? String(block.subtitle) : null,
    payload: block,
  };
}
