import MarkdownBody from "./MarkdownBody";
import type { ChatMessage } from "../types";

export default function ChatPane({
  messages,
  draft,
  busy,
  error,
  showReasoning,
  onDraft,
  onSend,
  onStop,
  onToggleReasoning,
}: {
  messages: ChatMessage[];
  draft: string;
  busy: boolean;
  error: string | null;
  showReasoning: boolean;
  onDraft: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
  onToggleReasoning: () => void;
}) {
  return (
    <section className={`chat${showReasoning ? " reasoning-on" : ""}`}>
      <div className="pane-header">
        <span>Session</span>
        <div className="pane-actions">
          <button
            type="button"
            className={`toggle${showReasoning ? " on" : ""}`}
            onClick={onToggleReasoning}
            aria-pressed={showReasoning}
          >
            Reasoning {showReasoning ? "on" : "off"}
          </button>
          <span>{busy ? "in progress" : "idle"}</span>
        </div>
      </div>
      <div className="messages">
        {messages.length === 0 ? (
          <div className="empty">
            <h2>Research question</h2>
            <p>
              Pin a horizon, then ask for the latest Baltic print, a segment split, or an outlook vintage.
            </p>
          </div>
        ) : null}
        {messages.map((message) => (
          <article key={message.id} className={`msg ${message.role}`}>
            <div className="role">{message.role === "user" ? "You" : "Analyst"}</div>
            {message.progress.length ? (
              <div className="progress-list">
                {message.progress.map((item) => (
                  <div key={item.id} className={`progress ${item.status}`}>
                    <span className="dot" />
                    <span>{item.label}</span>
                  </div>
                ))}
              </div>
            ) : null}
            {showReasoning && message.reasoning ? (
              <div className="reasoning">
                <div className="role">Reasoning</div>
                {message.reasoning}
              </div>
            ) : null}
            {message.role === "assistant" && message.content ? (
              <div className="body">
                <MarkdownBody>{message.content}</MarkdownBody>
              </div>
            ) : null}
            {message.role === "user" ? <div className="body">{message.content}</div> : null}
          </article>
        ))}
      </div>
      {error ? <div className="err">{error}</div> : null}
      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault();
          if (!busy) onSend();
        }}
      >
        <textarea
          value={draft}
          placeholder="Ask a follow-up, challenge a vintage, or pin a new horizon."
          onChange={(event) => onDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              if (!busy) onSend();
            }
          }}
        />
        {busy ? (
          <button type="button" className="stop" onClick={onStop}>
            STOP
          </button>
        ) : (
          <button type="submit" disabled={!draft.trim()}>
            SEND
          </button>
        )}
      </form>
    </section>
  );
}
