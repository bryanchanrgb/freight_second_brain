import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Artifact } from "../types";

type Point = { x: string | number; y: number };
type Series = { name: string; points: Point[] };

const COLORS = ["#e0b144", "#4cc3e8", "#3dd68c", "#ef6b78", "#c084fc", "#f0a35e", "#8b97ab"];

export function mergeSeries(seriesList: Series[]) {
  const keys = seriesList.map((item, index) => ({
    key: `s${index}`,
    name: item.name?.trim() || `Series ${index + 1}`,
    color: COLORS[index % COLORS.length],
  }));
  const byX = new Map<string, Record<string, string | number>>();
  seriesList.forEach((item, index) => {
    for (const point of item.points ?? []) {
      if (point?.x == null || point?.y == null || Number.isNaN(Number(point.y))) continue;
      const x = String(point.x);
      const row = byX.get(x) ?? { x };
      row[keys[index].key] = Number(point.y);
      byX.set(x, row);
    }
  });
  const rows = [...byX.values()].sort((a, b) =>
    String(a.x).localeCompare(String(b.x), undefined, { numeric: true }),
  );
  return { rows, keys };
}

export default function PrintsChart({ artifact, fresh = false }: { artifact: Artifact; fresh?: boolean }) {
  const payload = artifact.payload as {
    x_label?: string;
    y_label?: string;
    series?: Series[];
  };
  const seriesList = (payload.series ?? []).filter((item) => (item.points ?? []).length > 0);
  const { rows, keys } = mergeSeries(seriesList);
  if (!rows.length || !keys.length) return null;

  const multi = keys.length > 1;
  const Chart = multi ? LineChart : AreaChart;

  return (
    <section className={`chart-wrap${fresh ? " fresh" : ""}`}>
      <h2>{artifact.title}</h2>
      {artifact.subtitle ? <div className="caption">{artifact.subtitle}</div> : null}
      <div style={{ height: multi ? 300 : 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          <Chart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: multi ? 8 : 0 }}>
            <defs>
              {keys.map((item) => (
                <linearGradient key={item.key} id={`fill-${item.key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={item.color} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={item.color} stopOpacity={0} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid stroke="#232a38" strokeDasharray="3 3" />
            <XAxis dataKey="x" tick={{ fill: "#8b97ab", fontSize: 11 }} />
            <YAxis
              tick={{ fill: "#8b97ab", fontSize: 11 }}
              domain={["auto", "auto"]}
              tickFormatter={(v) => Number(v).toLocaleString()}
              width={64}
              label={{
                value: payload.y_label ?? (multi ? "Value" : "Index"),
                angle: -90,
                position: "insideLeft",
                fill: "#8b97ab",
                fontSize: 11,
              }}
            />
            <Tooltip
              contentStyle={{ background: "#10141c", border: "1px solid #252c3a", color: "#e6edf7" }}
              formatter={(value, name) => [Number(value).toLocaleString(), String(name)]}
            />
            {multi ? <Legend wrapperStyle={{ color: "#8b97ab", fontSize: 11 }} /> : null}
            {multi
              ? keys.map((item) => (
                  <Line
                    key={item.key}
                    type="monotone"
                    dataKey={item.key}
                    name={item.name}
                    stroke={item.color}
                    strokeWidth={2}
                    dot={{ r: 3, fill: item.color }}
                    activeDot={{ r: 5 }}
                    connectNulls
                  />
                ))
              : keys.map((item) => (
                  <Area
                    key={item.key}
                    type="monotone"
                    dataKey={item.key}
                    name={item.name}
                    stroke={item.color}
                    fill={`url(#fill-${item.key})`}
                    strokeWidth={2}
                    dot={{ r: 3, fill: item.color }}
                    activeDot={{ r: 5 }}
                    connectNulls
                  />
                ))}
          </Chart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
