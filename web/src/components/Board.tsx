import type { Artifact, BoardDisplay, ReportBlock } from "../types";
import ReportBlocks from "./ReportBlocks";

export default function Board({
  artifacts,
  display,
}: {
  artifacts: Artifact[];
  display: BoardDisplay;
}) {
  const report =
    artifacts.find((item) => item.kind === "report" && item.status !== "superseded") ??
    artifacts.find((item) => item.kind === "report");
  const blocks = Array.isArray(report?.payload?.blocks) ? (report?.payload?.blocks as ReportBlock[]) : [];
  const show = Boolean(report) && (display.showReport || blocks.length > 0);

  return (
    <section className="board">
      <div className="pane-header">
        <span>Report</span>
        <span>{display.turn ? `turn ${display.turn}` : "awaiting query"}</span>
      </div>
      <div className="board-body">
        {show && report ? (
          <article className={`report${isFresh(report, display.turn) ? " fresh" : ""}`}>
            <header className="report-head">
              <h1>{report.title}</h1>
              {report.subtitle ? <p className="caption">{report.subtitle}</p> : null}
            </header>
            <ReportBlocks blocks={blocks} />
          </article>
        ) : (
          <div className="empty">
            <h2>No report yet</h2>
            <p>The agent writes a readable note here — prose, tables, charts, and citations — after the first answer.</p>
          </div>
        )}
      </div>
    </section>
  );
}

function isFresh(artifact: Artifact, turn: number) {
  return Number(artifact.payload?.origin_turn ?? 0) === turn && turn > 0;
}
