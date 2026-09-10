import { useEffect, useMemo, useState } from "react";
import type { Artifact, BoardDisplay, Citation, ReportBlock } from "../types";
import { CiteContext } from "./MarkdownBody";
import ReportBlocks from "./ReportBlocks";
import SourcesPanel from "./SourcesPanel";

export default function Board({
  artifacts,
  display,
  onClose,
}: {
  artifacts: Artifact[];
  display: BoardDisplay;
  onClose?: () => void;
}) {
  const reports = useMemo(
    () =>
      artifacts
        .filter((item) => item.kind === "report")
        .sort((a, b) => Number(a.payload?.turn ?? 0) - Number(b.payload?.turn ?? 0)),
    [artifacts],
  );
  const latestId = reports.at(-1)?.id ?? null;
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusId, setFocusId] = useState<string | null>(null);
  const [activeCite, setActiveCite] = useState<number | null>(null);
  const [sourceScope, setSourceScope] = useState<"report" | "all">("report");

  useEffect(() => {
    if (display.activeReportId && reports.some((item) => item.id === display.activeReportId)) {
      setSelectedId(display.activeReportId);
      return;
    }
    if (latestId) setSelectedId((prev) => (prev && reports.some((item) => item.id === prev) ? prev : latestId));
  }, [display.activeReportId, latestId, reports]);

  const report = reports.find((item) => item.id === selectedId) ?? reports.at(-1);
  const blocks = Array.isArray(report?.payload?.blocks) ? (report?.payload?.blocks as ReportBlock[]) : [];
  const citations = (Array.isArray(report?.payload?.citations) ? report?.payload?.citations : []) as Citation[];
  const reportTurn = Number(report?.payload?.turn ?? report?.payload?.origin_turn ?? 0);
  const citeById = useMemo(() => {
    const map: Record<string, number> = {};
    for (const item of citations) {
      if (item.id) map[item.id] = item.n;
    }
    return map;
  }, [citations]);
  const citedIds = useMemo(() => new Set(Object.keys(citeById)), [citeById]);

  const sourceCards = artifacts.filter((item) => item.kind === "source_card");
  const scopedSources = useMemo(() => {
    if (sourceScope === "all" || !report) return sourceCards;
    return sourceCards.filter((card) => {
      if (citedIds.has(card.id)) return true;
      const origin = Number(card.payload?.origin_turn ?? 0);
      return reportTurn > 0 && origin === reportTurn;
    });
  }, [sourceCards, sourceScope, report, citedIds, reportTurn]);

  function openCite(n: number) {
    const hit = citations.find((item) => item.n === n);
    const id = hit?.id;
    if (!id) return;
    setActiveCite(n);
    setSourceScope("report");
    setFocusId(id);
    window.requestAnimationFrame(() => {
      document.getElementById(`source-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }

  function focusSource(id: string | null) {
    setFocusId(id);
    if (!id) {
      setActiveCite(null);
      return;
    }
    const n = citeById[id];
    if (!n) return;
    setActiveCite(n);
    window.requestAnimationFrame(() => {
      document.querySelector(`[data-cite="${n}"]`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }

  const show = Boolean(report) && (display.showReport || blocks.length > 0 || reports.length > 0);

  return (
    <section
      className={`board${onClose ? " overlay" : ""}`}
      {...(onClose
        ? { role: "dialog", "aria-modal": true, "aria-labelledby": "report-heading" }
        : {})}
    >
      <div className="pane-header">
        <span id="report-heading">Report</span>
        <div className="pane-actions">
          <span className="pane-status">{display.turn ? `turn ${display.turn}` : "awaiting query"}</span>
          {onClose ? (
            <button type="button" className="toggle overlay-close" onClick={onClose} autoFocus>
              Close
            </button>
          ) : null}
        </div>
      </div>
      {reports.length > 1 ? (
        <div className="report-history" role="tablist" aria-label="Report history">
          {reports.map((item) => {
            const turn = Number(item.payload?.turn ?? 0);
            const active = item.id === report?.id;
            return (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={active}
                className={`history-tab${active ? " active" : ""}`}
                onClick={() => {
                  setSelectedId(item.id);
                  focusSource(null);
                }}
              >
                {turn ? `T${turn}` : item.id} · {item.title}
              </button>
            );
          })}
        </div>
      ) : null}
      <div className="board-body">
        {show && report ? (
          <CiteContext.Provider value={{ onCite: openCite, activeCite }}>
            <article className="report">
              <header className="report-head">
                <h1>{report.title}</h1>
                {report.subtitle ? <p className="caption">{report.subtitle}</p> : null}
              </header>
              <ReportBlocks blocks={blocks} />
            </article>
            <div className="sources-toolbar">
              <button
                type="button"
                className={`toggle${sourceScope === "report" ? " on" : ""}`}
                onClick={() => setSourceScope("report")}
              >
                This report
              </button>
              <button
                type="button"
                className={`toggle${sourceScope === "all" ? " on" : ""}`}
                onClick={() => setSourceScope("all")}
              >
                All sources
              </button>
            </div>
            <SourcesPanel
              artifacts={scopedSources}
              citeById={citeById}
              focusId={focusId}
              onFocus={focusSource}
            />
          </CiteContext.Provider>
        ) : (
          <div className="empty">
            <h2>No report yet</h2>
            <p>The agent writes a readable note here — prose, tables, charts, and a labelled source list — after the first answer.</p>
          </div>
        )}
      </div>
    </section>
  );
}
