import type { Artifact } from "../types";

export type SourceTag = {
  dimension: string;
  id: string;
  value?: string;
  label: string;
};

export const DIM_LABEL: Record<string, string> = {
  provenance: "Standing",
  claim_type: "Kind",
  polarity: "Stance",
  freshness: "Vintage",
  medium: "Form",
  hierarchy: "Independence",
};

export const DIM_ORDER = ["provenance", "claim_type", "polarity", "freshness", "medium", "hierarchy"] as const;

export const TAG_TAXONOMY: SourceTag[] = [
  { dimension: "provenance", id: "provenance:primary", value: "primary", label: "Primary" },
  { dimension: "provenance", id: "provenance:secondary", value: "secondary", label: "Secondary" },
  { dimension: "provenance", id: "provenance:tertiary", value: "tertiary", label: "Tertiary" },
  { dimension: "provenance", id: "provenance:overlay", value: "overlay", label: "Overlay" },
  { dimension: "claim_type", id: "claim_type:observation", value: "observation", label: "Fact" },
  { dimension: "claim_type", id: "claim_type:explanation", value: "explanation", label: "Analysis" },
  { dimension: "claim_type", id: "claim_type:forecast", value: "forecast", label: "Outlook" },
  { dimension: "claim_type", id: "claim_type:scenario", value: "scenario", label: "Scenario" },
  { dimension: "claim_type", id: "claim_type:risk", value: "risk", label: "Risk" },
  { dimension: "claim_type", id: "claim_type:methodology", value: "methodology", label: "Methodology" },
  { dimension: "polarity", id: "polarity:bullish", value: "bullish", label: "Bullish" },
  { dimension: "polarity", id: "polarity:bearish", value: "bearish", label: "Bearish" },
  { dimension: "polarity", id: "polarity:mixed", value: "mixed", label: "Mixed" },
  { dimension: "polarity", id: "polarity:neutral", value: "neutral", label: "Neutral" },
  { dimension: "freshness", id: "freshness:current", value: "current", label: "Current" },
  { dimension: "freshness", id: "freshness:recent", value: "recent", label: "Recent" },
  { dimension: "freshness", id: "freshness:aging", value: "aging", label: "Aging" },
  { dimension: "freshness", id: "freshness:historical_vintage", value: "historical_vintage", label: "Historical" },
  { dimension: "medium", id: "medium:website", value: "website", label: "Web" },
  { dimension: "medium", id: "medium:pdf", value: "pdf", label: "PDF" },
  { dimension: "medium", id: "medium:rss", value: "rss", label: "News feed" },
  { dimension: "hierarchy", id: "hierarchy:primary", value: "primary", label: "Lead" },
  { dimension: "hierarchy", id: "hierarchy:duplicate", value: "duplicate", label: "Reprint" },
];

const ROLE_PROVENANCE: Record<string, string> = {
  primary: "primary",
  reprint: "secondary",
  secondary: "secondary",
  tertiary: "tertiary",
  overlay: "overlay",
};

const LABELS: Record<string, string> = Object.fromEntries(TAG_TAXONOMY.map((tag) => [tag.id, tag.label]));

function makeTag(dimension: string, value: string): SourceTag | null {
  if (!value) return null;
  const id = `${dimension}:${value}`;
  return { dimension, id, value, label: LABELS[id] || value.replace(/_/g, " ") };
}

export function inferTags(payload: Record<string, unknown>): SourceTag[] {
  const tags: SourceTag[] = [];
  const add = (dimension: string, value: unknown) => {
    const tag = makeTag(dimension, String(value || ""));
    if (tag) tags.push(tag);
  };
  const role = String(payload.role || "");
  add("provenance", payload.provenance || ROLE_PROVENANCE[role]);
  add("hierarchy", payload.hierarchy === "duplicate" ? "duplicate" : payload.hierarchy ? "primary" : "");
  add("claim_type", payload.claim_type);
  add("polarity", payload.polarity && payload.polarity !== "unknown" ? payload.polarity : "");
  add("freshness", payload.freshness);
  add("medium", payload.medium);
  return tags.filter((tag) => DIM_ORDER.includes(tag.dimension as (typeof DIM_ORDER)[number]));
}

export function tagsOf(artifact: Artifact): SourceTag[] {
  const raw = artifact.payload.tags;
  if (Array.isArray(raw) && raw.length) {
    return raw.filter(
      (item): item is SourceTag => Boolean(item && typeof item === "object" && "id" in item && "label" in item),
    );
  }
  return inferTags(artifact.payload);
}

export function tagIdsOf(artifact: Artifact): string[] {
  const ids = artifact.payload.tag_ids;
  if (Array.isArray(ids) && ids.length) return ids.map(String);
  return tagsOf(artifact).map((tag) => tag.id);
}

export function TagPills({
  tags,
  selected = [],
  onToggle,
}: {
  tags: SourceTag[];
  selected?: string[];
  onToggle?: (id: string) => void;
}) {
  if (!tags.length) return null;
  return (
    <div className="tag-row">
      {tags.map((tag) => {
        const active = selected.includes(tag.id);
        const className = `tag${active ? " active" : ""}${onToggle ? " clickable" : ""}`;
        if (!onToggle) {
          return (
            <span key={tag.id} className={className}>
              {tag.label}
            </span>
          );
        }
        return (
          <button
            key={tag.id}
            type="button"
            className={className}
            onClick={() => onToggle(tag.id)}
            aria-pressed={active}
          >
            {tag.label}
          </button>
        );
      })}
    </div>
  );
}
