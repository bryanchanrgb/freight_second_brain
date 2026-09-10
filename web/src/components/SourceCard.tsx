import { memo, useMemo } from "react";
import type { Artifact } from "../types";
import { TagPills, tagsOf } from "./TagPills";

const SourceCard = memo(function SourceCard({
  artifact,
  compact = false,
  onToggleTag,
  citeN,
  focused = false,
  onActivate,
}: {
  artifact: Artifact;
  compact?: boolean;
  onToggleTag?: (id: string) => void;
  citeN?: number;
  focused?: boolean;
  onActivate?: () => void;
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
  const tags = useMemo(
    () => tagsOf(artifact).filter((tag) => tag.dimension !== "access" && tag.dimension !== "channel"),
    [artifact],
  );
  const print = payload.print ? payload.print.toLocaleString() : null;
  const snip = payload.one_liner || payload.snippet || "";
  return (
    <article
      className={`card${superseded ? " superseded" : ""}${compact ? " reprint" : ""}${focused ? " focused" : ""}`}
      onClick={onActivate}
    >
      <div className="card-head">
        {citeN ? <span className="cite-badge">{citeN}</span> : null}
        <h3>{artifact.title}</h3>
        {print ? <span className="mono">{print}</span> : null}
      </div>
      <div className="card-meta">
        <TagPills tags={tags} onToggle={onToggleTag} />
      </div>
      {focused && snip ? <p className="snip">{snip}</p> : null}
      <PrettyLink href={href} host={payload.pretty_host} path={payload.pretty_path} />
    </article>
  );
});

export default SourceCard;

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
    <a className="pretty-url" href={href} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>
      <span className="url-host">{host || href.replace(/^https?:\/\//, "").split("/")[0]}</span>
      {path ? <span className="url-path">{path}</span> : null}
    </a>
  );
}
