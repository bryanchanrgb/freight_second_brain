import { useMemo, useState } from "react";
import type { Artifact } from "../types";

type Col = { key: string; label: string };

export default function PrintsTable({ artifact, fresh = false }: { artifact: Artifact; fresh?: boolean }) {
  const payload = artifact.payload as {
    columns?: Col[];
    rows?: Record<string, unknown>[];
    numeric?: string[];
  };
  const columns = payload.columns ?? [];
  const rows = payload.rows ?? [];
  const numeric = new Set(payload.numeric ?? ["value"]);
  const [sort, setSort] = useState<{ key: string; dir: number }>({ key: columns[0]?.key ?? "", dir: 1 });

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = a[sort.key];
      const bv = b[sort.key];
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * sort.dir;
      return String(av ?? "").localeCompare(String(bv ?? "")) * sort.dir;
    });
    return copy;
  }, [rows, sort]);

  if (!columns.length) return null;

  return (
    <section className={`table-wrap${fresh ? " fresh" : ""}`}>
      <h2>{artifact.title}</h2>
      {artifact.subtitle ? <div className="caption">{artifact.subtitle}</div> : null}
      <table className="data">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                onClick={() =>
                  setSort((prev) => ({
                    key: col.key,
                    dir: prev.key === col.key ? -prev.dir : 1,
                  }))
                }
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, idx) => (
            <tr key={idx}>
              {columns.map((col) => (
                <td key={col.key} className={numeric.has(col.key) ? "num" : undefined}>
                  {formatCell(row[col.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function formatCell(value: unknown) {
  if (value == null) return "—";
  if (typeof value === "number") return value.toLocaleString();
  return String(value);
}
