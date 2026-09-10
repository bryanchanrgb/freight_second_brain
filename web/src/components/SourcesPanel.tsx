import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import type { Artifact } from "../types";
import SourceCard from "./SourceCard";
import { TagPills, DIM_LABEL, DIM_ORDER, TAG_TAXONOMY, tagIdsOf } from "./TagPills";

export type SourceGroup = {
  id: string;
  primary: Artifact;
  duplicates: Artifact[];
  rank: number;
  citeN?: number;
};

export default function SourcesPanel({
  artifacts,
  citeById,
  focusId,
  onFocus,
}: {
  artifacts: Artifact[];
  citeById: Record<string, number>;
  focusId: string | null;
  onFocus: (id: string | null) => void;
}) {
  const groups = useMemo(() => groupSources(artifacts, citeById), [artifacts, citeById]);
  const [selected, setSelected] = useState<string[]>([]);
  const deferredSelected = useDeferredValue(selected);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const focusWhenSet = useRef<string | null>(null);

  const visible = useMemo(
    () => groups.filter((group) => groupMatches(group, deferredSelected)),
    [groups, deferredSelected],
  );
  const cited = useMemo(() => visible.filter((group) => group.citeN != null), [visible]);
  const other = useMemo(() => visible.filter((group) => group.citeN == null), [visible]);

  useEffect(() => {
    const changed = focusWhenSet.current !== focusId;
    focusWhenSet.current = focusId;
    if (!changed || !focusId) return;
    const exists = groups.some((group) => memberIds(group).includes(focusId));
    const shown = visible.some((group) => memberIds(group).includes(focusId));
    if (exists && !shown) setSelected([]);
  }, [focusId, groups, visible]);

  const toggle = useCallback((id: string) => {
    setSelected((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  }, []);

  if (!groups.length) {
    return (
      <div className="empty sources-empty">
        <h2>No sources yet</h2>
        <p>Fetched articles are tagged and listed here. Numbered marks in the report open the matching card.</p>
      </div>
    );
  }

  return (
    <section className="sources-panel">
      <div className="sources-head">
        <h2>Sources</h2>
        <span className="caption">{visible.length} of {groups.length} groups</span>
      </div>
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
      {visible.length === 0 ? (
        <div className="empty">
          <h2>No matching sources</h2>
          <p>Clear a tag filter to see the rest of the list.</p>
        </div>
      ) : null}
      {cited.length && other.length ? <p className="caption source-section">Cited in this report</p> : null}
      {cited.map((group) => (
        <SourceGroup
          key={group.id}
          group={group}
          citeById={citeById}
          focusId={focusId}
          onToggleTag={toggle}
          onFocus={onFocus}
        />
      ))}
      {cited.length && other.length ? <p className="caption source-section">Other sources</p> : null}
      {other.map((group) => (
        <SourceGroup
          key={group.id}
          group={group}
          citeById={citeById}
          focusId={focusId}
          onToggleTag={toggle}
          onFocus={onFocus}
        />
      ))}
    </section>
  );
}

function SourceGroup({
  group,
  citeById,
  focusId,
  onToggleTag,
  onFocus,
}: {
  group: SourceGroup;
  citeById: Record<string, number>;
  focusId: string | null;
  onToggleTag: (id: string) => void;
  onFocus: (id: string | null) => void;
}) {
  const focusedHere = memberIds(group).includes(focusId || "");
  const [open, setOpen] = useState(focusedHere);
  const activatePrimary = useCallback(() => onFocus(group.primary.id), [onFocus, group.primary.id]);
  useEffect(() => {
    if (focusedHere) setOpen(true);
  }, [focusedHere, focusId]);
  return (
    <div className="source-group">
      <div id={`source-${group.primary.id}`}>
        <SourceCard
          artifact={group.primary}
          onToggleTag={onToggleTag}
          citeN={citeById[group.primary.id]}
          focused={focusId === group.primary.id}
          onActivate={activatePrimary}
        />
      </div>
      {group.duplicates.length ? (
        <div className="dupes">
          <button type="button" className="expand" onClick={() => setOpen((value) => !value)}>
            {open ? "Hide" : "Show"} {group.duplicates.length}{" "}
            {group.duplicates.length === 1 ? "reprint / secondary source" : "reprints / secondary sources"}
          </button>
          {open
            ? group.duplicates.map((item) => (
                <DuplicateCard
                  key={item.id}
                  item={item}
                  citeN={citeById[item.id]}
                  focused={focusId === item.id}
                  onToggleTag={onToggleTag}
                  onFocus={onFocus}
                />
              ))
            : null}
        </div>
      ) : null}
    </div>
  );
}

function DuplicateCard({
  item,
  citeN,
  focused,
  onToggleTag,
  onFocus,
}: {
  item: Artifact;
  citeN?: number;
  focused: boolean;
  onToggleTag: (id: string) => void;
  onFocus: (id: string | null) => void;
}) {
  const activate = useCallback(() => onFocus(item.id), [onFocus, item.id]);
  return (
    <div id={`source-${item.id}`}>
      <SourceCard
        artifact={item}
        compact
        onToggleTag={onToggleTag}
        citeN={citeN}
        focused={focused}
        onActivate={activate}
      />
    </div>
  );
}

function memberIds(group: SourceGroup) {
  return [group.primary.id, ...group.duplicates.map((item) => item.id)];
}

function citeNFor(items: Artifact[], citeById: Record<string, number>): number | undefined {
  const nums = items.map((item) => citeById[item.id]).filter((n): n is number => typeof n === "number");
  return nums.length ? Math.min(...nums) : undefined;
}

function groupMatches(group: SourceGroup, selected: string[]) {
  if (!selected.length) return true;
  const byDim = new Map<string, string[]>();
  for (const id of selected) {
    const sep = id.indexOf(":");
    const dim = sep === -1 ? id : id.slice(0, sep);
    const list = byDim.get(dim) ?? [];
    list.push(id);
    byDim.set(dim, list);
  }
  return [group.primary, ...group.duplicates].some((card) => {
    const ids = tagIdsOf(card);
    return [...byDim.values()].every((options) => options.some((id) => ids.includes(id)));
  });
}

export function groupSources(cards: Artifact[], citeById: Record<string, number> = {}): SourceGroup[] {
  const active = cards.filter((item) => item.status !== "superseded");
  const buckets = new Map<string, Artifact[]>();
  for (const card of active) {
    const key = String(card.payload.independence_group || card.id);
    const list = buckets.get(key) ?? [];
    list.push(card);
    buckets.set(key, list);
  }
  const groups: SourceGroup[] = [];
  for (const [id, items] of buckets) {
    const ordered = [...items].sort((a, b) => {
      const ca = citeById[a.id] ?? Infinity;
      const cb = citeById[b.id] ?? Infinity;
      if (ca !== cb) return ca - cb;
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
      citeN: citeNFor(items, citeById),
    });
  }
  groups.sort((a, b) => {
    const ca = a.citeN ?? Infinity;
    const cb = b.citeN ?? Infinity;
    if (ca !== cb) return ca - cb;
    return a.rank - b.rank;
  });
  return groups;
}
