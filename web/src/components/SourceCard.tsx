import type { Artifact } from "../types";
import { TagPills, tagsOf } from "./TagPills";

export default function SourceCard({
  artifact,
  fresh,
  compact = false,
  selected = [],
  onToggleTag,
}: {
  artifact: Artifact;
  fresh: boolean;
  compact?: boolean;
  selected?: string[];
  onToggleTag?: (id: string) => void;
}) {
  const payload = artifact.payload as {
    url?: string;
    one_liner?: string;
    snippet?: string;
    print?: number | null;
    pretty_host?: string;
    pretty_path?: string;
    publisher?: string;
    role?: string;
    hierarchy?: string;
    freshness?: string;
  };
  const superseded = artifact.status === "superseded";
  const href = payload.url;
  const tags = tagsOf(artifact).filter((tag) => tag.dimension !== "access" && tag.dimension !== "channel");
  return (
    <article
      className={`card${superseded ? " superseded" : ""}${fresh ? " fresh" : ""}${compact ? " compact" : ""}`}
    >
      <div className="meta">
        <span className={`badge${payload.hierarchy === "primary" ? "" : " old"}`}>
          {labelFor(payload.role, payload.hierarchy)}
        </span>
        <span className="mono">{payload.print ? payload.print.toLocaleString() : "—"}</span>
      </div>
      <h3>{artifact.title}</h3>
      <p className="snip">{payload.one_liner || payload.snippet || ""}</p>
      <TagPills tags={tags} selected={selected} onToggle={onToggleTag} />
      <PrettyLink href={href} host={payload.pretty_host} path={payload.pretty_path} />
      <div className="meta">
        <span>{payload.publisher || artifact.subtitle || ""}</span>
        <span>{payload.freshness || ""}</span>
      </div>
    </article>
  );
}

function labelFor(role?: string, hierarchy?: string) {
  if (hierarchy === "duplicate") return "Reprint";
  if (role === "overlay") return "Overlay";
  if (role === "primary") return "Primary";
  if (role === "reprint") return "Secondary";
  if (role === "tertiary") return "Tertiary";
  return "Source";
}

export function PrettyLink({
  href,
  host,
  path,
}: {
  href?: string;
  host?: string;
  path?: string;
}) {
  if (!href) return null;
  return (
    <a className="pretty-url" href={href} target="_blank" rel="noreferrer">
      <span className="url-host">{host || href.replace(/^https?:\/\//, "").split("/")[0]}</span>
      {path ? <span className="url-path">{path}</span> : null}
    </a>
  );
}
