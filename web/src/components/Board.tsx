import { useMemo, useState } from "react";
import type { Artifact, BoardDisplay } from "../types";
import PrintsChart from "./PrintsChart";
import PrintsTable from "./PrintsTable";
import SourceCard from "./SourceCard";
import { TagPills, DIM_LABEL, DIM_ORDER, TAG_TAXONOMY, tagIdsOf } from "./TagPills";

type Group = {
  id: string;
  primary: Artifact;
  duplicates: Artifact[];
  rank: number;
};

export default function Board({
  artifacts,
  display,
}: {
  artifacts: Artifact[];
  display: BoardDisplay;
}) {
  const table = artifacts.find((item) => item.kind === "table" && item.status !== "superseded");
  const chart = artifacts.find((item) => item.kind === "chart" && item.status !== "superseded");
  const groups = useMemo(() => groupSources(artifacts.filter((item) => item.kind === "source_card")), [artifacts]);
  const [selected, setSelected] = useState<string[]>([]);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const visible = useMemo(
    () => groups.filter((group) => groupMatches(group, selected)),
    [groups, selected],
  );

  function toggle(id: string) {
    setSelected((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  }

  return (
    <section className="board">
      <div className="pane-header">
        <span>Sources</span>
        <span>{display.turn ? `turn ${display.turn}` : "awaiting query"}</span>
      </div>
      {groups.length ? (
        <div className="filters">
          <button
            type="button"
            className="filters-toggle"
            onClick={() => setFiltersOpen((value) => !value)}
            aria-expanded={filtersOpen}
          >
            <span>Filters{selected.length ? ` · ${selected.length} selected` : ""}</span>
            <span>{filtersOpen ? "Hide" : "Show"}</span>
          </button>
          {filtersOpen ? (
            <>
              {DIM_ORDER.map((dim) => {
                const tags = TAG_TAXONOMY.filter((tag) => tag.dimension === dim);
                return (
                  <div key={dim} className="filter-dim">
                    <span className="filter-label">{DIM_LABEL[dim] || dim}</span>
                    <TagPills tags={tags} selected={selected} onToggle={toggle} />
                  </div>
                );
              })}
              {selected.length ? (
                <button type="button" className="expand" onClick={() => setSelected([])}>
                  Clear filters
                </button>
              ) : null}
            </>
          ) : null}
        </div>
      ) : null}
      <div className="board-body">
        {display.showChart && chart ? <PrintsChart artifact={chart} fresh={isFresh(chart, display.turn)} /> : null}
        {groups.length === 0 && !display.showChart && !display.showTable ? (
          <div className="empty">
            <h2>No sources yet</h2>
            <p>Ranked primary sources will appear here after the first search.</p>
          </div>
        ) : null}
        {groups.length > 0 && visible.length === 0 ? (
          <div className="empty">
            <h2>No matching sources</h2>
            <p>Clear a tag filter to see the rest of the board.</p>
          </div>
        ) : null}
        {visible.map((group) => (
          <SourceGroup
            key={group.id}
            group={group}
            turn={display.turn}
            selected={selected}
            onToggleTag={toggle}
          />
        ))}
        {display.showTable && table ? <PrintsTable artifact={table} fresh={isFresh(table, display.turn)} /> : null}
      </div>
    </section>
  );
}

function SourceGroup({
  group,
  turn,
  selected,
  onToggleTag,
}: {
  group: Group;
  turn: number;
  selected: string[];
  onToggleTag: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const fresh = isFresh(group.primary, turn) || group.duplicates.some((item) => isFresh(item, turn));
  return (
    <div className={`source-group${fresh ? " fresh-group" : ""}`}>
      <SourceCard artifact={group.primary} fresh={isFresh(group.primary, turn)} selected={selected} onToggleTag={onToggleTag} />
      {group.duplicates.length ? (
        <div className="dupes">
          <button type="button" className="expand" onClick={() => setOpen((value) => !value)}>
            {open ? "Hide" : "Show"} {group.duplicates.length}{" "}
            {group.duplicates.length === 1 ? "reprint / secondary source" : "reprints / secondary sources"}
          </button>
          {open
            ? group.duplicates.map((item) => (
                <SourceCard
                  key={item.id}
                  artifact={item}
                  fresh={isFresh(item, turn)}
                  compact
                  selected={selected}
                  onToggleTag={onToggleTag}
                />
              ))
            : null}
        </div>
      ) : null}
    </div>
  );
}

function isFresh(artifact: Artifact, turn: number) {
  return Number(artifact.payload?.origin_turn ?? 0) === turn && turn > 0;
}

function groupMatches(group: Group, selected: string[]) {
  if (!selected.length) return true;
  const byDim = new Map<string, string[]>();
  for (const id of selected) {
    const dim = id.slice(0, id.indexOf(":"));
    const list = byDim.get(dim) ?? [];
    list.push(id);
    byDim.set(dim, list);
  }
  return [group.primary, ...group.duplicates].some((card) => {
    const ids = tagIdsOf(card);
    return [...byDim.values()].every((options) => options.some((id) => ids.includes(id)));
  });
}

function groupSources(cards: Artifact[]): Group[] {
  const active = cards.filter((item) => item.status !== "superseded");
  const buckets = new Map<string, Artifact[]>();
  for (const card of active) {
    const key = String(card.payload.independence_group || card.id);
    const list = buckets.get(key) ?? [];
    list.push(card);
    buckets.set(key, list);
  }
  const groups: Group[] = [];
  for (const [id, items] of buckets) {
    const ordered = [...items].sort((a, b) => {
      const ha = a.payload.hierarchy === "primary" ? 0 : 1;
      const hb = b.payload.hierarchy === "primary" ? 0 : 1;
      if (ha !== hb) return ha - hb;
      return Number(a.payload.rank ?? 9) - Number(b.payload.rank ?? 9);
    });
    const [primary, ...duplicates] = ordered;
    groups.push({
      id,
      primary,
      duplicates,
      rank: Number(primary.payload.rank ?? 9),
    });
  }
  groups.sort((a, b) => a.rank - b.rank);
  return groups;
}
