import MarkdownBody from "./MarkdownBody";
import type { ChatMessage } from "../types";
import { useState, type ReactNode } from "react";

const TIP_REASONING = "freight-sb-tip-reasoning";
const TIP_RESET = "freight-sb-tip-reset";

function tipSeen(key: string) {
  try {
    return localStorage.getItem(key) === "1";
  } catch {
    return true;
  }
}

function markTipSeen(key: string) {
  try {
    localStorage.setItem(key, "1");
  } catch {
    /* ignore quota / private mode */
  }
}

function TipButton({
  tipKey,
  tip,
  className,
  onClick,
  disabled,
  pressed,
  align = "start",
  children,
}: {
  tipKey: string;
  tip: string;
  className: string;
  onClick: () => void;
  disabled?: boolean;
  pressed?: boolean;
  align?: "start" | "end";
  children: ReactNode;
}) {
  const [show, setShow] = useState(() => !tipSeen(tipKey));

  function dismiss() {
    if (!show) return;
    setShow(false);
    markTipSeen(tipKey);
  }

  return (
    <span className={`tip-wrap${align === "end" ? " end" : ""}`}>
      <button
        type="button"
        className={className}
        onClick={onClick}
        onMouseEnter={dismiss}
        onFocus={dismiss}
        disabled={disabled}
        aria-pressed={pressed}
      >
        {children}
      </button>
      {show ? (
        <span className="tip" role="tooltip">
          {tip}
        </span>
      ) : null}
    </span>
  );
}

export default function ChatPane({
  messages,
  draft,
  busy,
  error,
  showReasoning,
  hasReport,
  onDraft,
  onSend,
  onStop,
  onReset,
  onToggleReasoning,
  onOpenReport,
}: {
  messages: ChatMessage[];
  draft: string;
  busy: boolean;
  error: string | null;
  showReasoning: boolean;
  hasReport?: boolean;
  onDraft: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
  onReset: () => void;
  onToggleReasoning: () => void;
  onOpenReport?: () => void;
}) {
  const canReset = messages.length > 0 || busy;
  return (
    <section className={`chat${showReasoning ? " reasoning-on" : ""}`}>
      <div className="pane-header">
        <span>Session</span>
        <div className="pane-actions">
          <TipButton
            tipKey={TIP_REASONING}
            tip="Show the agent's reasoning for this turn."
            className={`toggle${showReasoning ? " on" : ""}`}
            onClick={onToggleReasoning}
            pressed={showReasoning}
            align="end"
          >
            Reasoning {showReasoning ? "on" : "off"}
          </TipButton>
          {hasReport && onOpenReport ? (
            <button type="button" className="toggle on" onClick={onOpenReport}>
              View report
            </button>
          ) : null}
          <TipButton
            tipKey={TIP_RESET}
            tip="Start a fresh chat."
            className="toggle reset"
            onClick={onReset}
            disabled={!canReset}
          >
            Reset
          </TipButton>
          <span className="pane-status">{busy ? "in progress" : "idle"}</span>
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
        {messages.map((message) => {
          const thinking =
            message.role === "assistant" &&
            Boolean(message.streaming) &&
            !message.content &&
            !message.progress.some((item) => item.status === "running");
          return (
          <article key={message.id} className={`msg ${message.role}`}>
            <div className="role">{message.role === "user" ? "You" : "Analyst"}</div>
            {thinking ? (
              <div className="thinking" aria-live="polite">
                Thinking
                <span className="thinking-dots" aria-hidden="true">
                  <span>.</span>
                  <span>.</span>
                  <span>.</span>
                </span>
              </div>
            ) : null}
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
                <MarkdownBody onOpenReport={onOpenReport}>{message.content}</MarkdownBody>
              </div>
            ) : null}
            {message.role === "user" ? <div className="body">{message.content}</div> : null}
          </article>
          );
        })}
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
