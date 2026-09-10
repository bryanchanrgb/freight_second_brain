import {
  FUTURE_SOURCES,
  MARKET_TOOLS,
  PRESS_SOURCES,
  WEB_TOOLS,
  type ParamSpec,
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
            agent to fetch those sources, read them, and answer your question with citations.
          </p>

          <h2>Why generative AI</h2>
          <p>
            A language model can work through large volumes of text — extracting a print, a segment split,
            or an outlook vintage from articles and PDFs. The same tools serve different questions: a session
            print, a market driver, or a longer horizon. You are not limited to a fixed set of charts.
          </p>
          <p>
            The agent does not invent forecasts. Figures are quoted from sources and labelled by vintage.
          </p>

          <h2>How it works</h2>
          <p>
            Data access is through tools: a market feed for dated prints, integrated press sites for news,
            plus web search and a URL reader for other public material. New sources are added as tools, not
            by retraining the model.
          </p>

          <h2>This interface</h2>
          <ul>
            <li><strong>Chat</strong> — multi-turn conversation on the left.</li>
            <li><strong>Report</strong> — a structured note on the right with prose, tables, and charts.</li>
            <li><strong>Sources</strong> — labelled cards with citations linked to the report.</li>
          </ul>
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
          <p className="caption">
            <code>press_fetch</code> — pin a category or the whole site is returned.{" "}
            <code>press_catalog</code> lists desks and parameters.
          </p>
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
            <SourceDetails key={source.id} source={source} compact />
          ))}
        </div>
      </div>
    </section>
  );
}

function SourceDetails({ source, compact = false }: { source: SourceSpec; compact?: boolean }) {
  return (
    <details className="guide-source">
      <summary>
        <span className="guide-source-name">{source.name}</span>
        <span className="tag">{source.tool}</span>
      </summary>
      <div className="guide-source-body">
        <p>{source.summary}</p>
        <p>
          <strong>Provides.</strong> {source.provides}
        </p>
        {!compact && source.params && source.params.length > 0 ? <ParamTable params={source.params} /> : null}
        {!compact && source.categories?.length ? (
          <dl className="guide-cats">
            {source.categories.map((cat) => (
              <div key={cat.id} className="guide-cat">
                <dt>
                  <code>{cat.id}</code>
                </dt>
                <dd>{cat.detail}</dd>
              </div>
            ))}
          </dl>
        ) : null}
        {source.notes ? <p className="caption">{source.notes}</p> : null}
      </div>
    </details>
  );
}

function ParamTable({ params }: { params: ParamSpec[] }) {
  return (
    <table className="data">
      <thead>
        <tr>
          <th>Parameter</th>
          <th>Type</th>
          <th>Description</th>
        </tr>
      </thead>
      <tbody>
        {params.map((param) => (
          <tr key={param.name}>
            <td>
              <code>{param.name}</code>
              {param.required ? <span className="guide-req"> required</span> : null}
            </td>
            <td className="mono">{param.type}</td>
            <td>{param.detail}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
