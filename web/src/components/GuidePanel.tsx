import {
  FUTURE_SOURCES,
  MARKET_TOOLS,
  PRESS_SOURCES,
  WEB_TOOLS,
  type SourceSpec,
} from "../guide";

export default function GuidePanel({ onHide }: { onHide: () => void }) {
  return (
    <section className="guide" id="desk-guide" aria-label="Introduction and data sources">
      <div className="guide-col intro">
        <div className="guide-col-head">
          <span>Introduction</span>
          <button type="button" className="toggle on" onClick={onHide}>
            Hide guide
          </button>
        </div>
        <div className="guide-body">
          <h1>Dry-bulk freight research desk</h1>
          <p>
            A second brain for analyzing freight information. News, commentary, broker weeklies, outlook
            reports, and cargo notes carry signal that traditional models rarely ingest. This desk uses an
            agent to fetch those sources, read them, and answer your question with citations. The agent does
            not invent forecasts.
          </p>

          <h2>How it works</h2>
          <p>
            Data access is through tools: a market feed for dated prints, integrated press sites for news,
            plus web search and a URL reader for other public material. New sources are added as tools, not
            by retraining the model.
          </p>

          <h2>This interface</h2>
          <ul>
            <li><strong>Chat</strong> — multi-turn conversation.</li>
            <li>
              <strong>Report</strong> — a structured note with prose, tables, and charts. On a phone, open it
              from “See the report” in the reply.
            </li>
            <li><strong>Sources</strong> — labelled cards with citations linked to the report.</li>
          </ul>

          <h2>Future vision</h2>
          <p>
            Identify signals in unstructured qualitative data that financial models miss. Test those
            signals against history to prove they add value. Integrate internal sources for a competitive
            edge.
          </p>
          <button type="button" className="guide-start" onClick={onHide}>
            Start researching
          </button>
        </div>
      </div>

      <div className="guide-col spec">
        <div className="guide-col-head">
          <span>Data sources</span>
          <span className="caption">Collapsible spec</span>
        </div>
        <div className="guide-body">
          <p>
            The agent calls these tools at question time. Prints come from the market feed; press sites and
            search cover news and analysis.
          </p>

          <h2>Market data</h2>
          {MARKET_TOOLS.map((source) => (
            <SourceDetails key={source.id} source={source} />
          ))}

          <h2>Press sites</h2>
          <p className="caption">News and commentary from these publishers.</p>
          {PRESS_SOURCES.map((source) => (
            <SourceDetails key={source.id} source={source} />
          ))}

          <h2>Search and read</h2>
          {WEB_TOOLS.map((source) => (
            <SourceDetails key={source.id} source={source} />
          ))}

          <h2>Future access</h2>
          <p className="caption">Not integrated on this desk.</p>
          {FUTURE_SOURCES.map((source) => (
            <SourceDetails key={source.id} source={source} />
          ))}
        </div>
      </div>
    </section>
  );
}

function SourceDetails({ source }: { source: SourceSpec }) {
  return (
    <details className="guide-source">
      <summary>
        <span className="guide-source-name">{source.name}</span>
        <span className="tag">{source.tool}</span>
      </summary>
      <div className="guide-source-body">
        <p>{source.summary}</p>
        <p>
          <strong>Provides:</strong> {source.provides}
        </p>
        {source.notes ? <p className="caption">{source.notes}</p> : null}
      </div>
    </details>
  );
}
