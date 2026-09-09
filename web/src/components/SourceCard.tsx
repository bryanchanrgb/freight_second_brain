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
  };
  const superseded = artifact.status === "superseded";
  const href = payload.url;
  const tags = tagsOf(artifact).filter((tag) => tag.dimension !== "access" && tag.dimension !== "channel");
  const print = payload.print ? payload.print.toLocaleString() : null;
  return (
    <article
      className={`card${superseded ? " superseded" : ""}${fresh ? " fresh" : ""}${compact ? " compact" : ""}`}
    >
      <TagPills tags={tags} selected={selected} onToggle={onToggleTag} />
      <div className="card-head">
        <h3>{artifact.title}</h3>
        {print ? <span className="mono">{print}</span> : null}
      </div>
      <p className="snip">{payload.one_liner || payload.snippet || ""}</p>
      <PrettyLink href={href} host={payload.pretty_host} path={payload.pretty_path} />
    </article>
  );
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
