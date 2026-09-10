import { useEffect, useMemo, useRef, useState, type Dispatch, type FormEvent, type SetStateAction } from "react";
import Board from "./components/Board";
import ChatPane from "./components/ChatPane";
import GuidePanel from "./components/GuidePanel";
import { createSession, fetchAuth, fetchHealth, loginDesk, stopSession, streamMessage } from "./api";
import { friendlyDeskError } from "./errors";
import type { Artifact, BoardDisplay, ChatMessage, DeskEvent, Progress } from "./types";

const GUIDE_KEY = "freight-sb-guide-open";
const STARTER_DRAFT =
  "As of today, horizon session/week: what is the latest Baltic Dry Index print, and how did Capesize and Panamax split?";

function artifactsRecord(items: Artifact[] | undefined): Record<string, Artifact> {
  const next: Record<string, Artifact> = {};
  for (const item of items || []) {
    if (item?.id) next[item.id] = item;
  }
  return next;
}

function readGuideOpen() {
  try {
    const raw = localStorage.getItem(GUIDE_KEY);
    if (raw === null) return true;
    return raw === "1";
  } catch {
    return true;
  }
}

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [health, setHealth] = useState<{ model: string; exa_backend: string } | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [artifacts, setArtifacts] = useState<Record<string, Artifact>>({});
  const [display, setDisplay] = useState<BoardDisplay>({ showReport: false, turn: 0, activeReportId: null });
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showReasoning, setShowReasoning] = useState(false);
  const [guideOpen, setGuideOpen] = useState(readGuideOpen);
  const [locked, setLocked] = useState(false);
  const [accessToken, setAccessToken] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const assistantIdRef = useRef<string | null>(null);

  function setGuide(open: boolean) {
    setGuideOpen(open);
    try {
      localStorage.setItem(GUIDE_KEY, open ? "1" : "0");
    } catch {
      /* ignore quota / private mode */
    }
  }

  async function hydrateSession(preload: boolean) {
    const created = await createSession(preload);
    setSessionId(created.session_id);
    if (created.preloaded) {
      setMessages(created.messages || []);
      setArtifacts(artifactsRecord(created.artifacts));
      setDisplay(created.display || { showReport: false, turn: 0, activeReportId: null });
      setDraft("");
      try {
        if (localStorage.getItem(GUIDE_KEY) === null) setGuideOpen(false);
      } catch {
        setGuideOpen(false);
      }
    } else {
      setDraft(STARTER_DRAFT);
    }
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const status = await fetchHealth();
        if (cancelled) return;
        setHealth({ model: status.model, exa_backend: status.exa_backend });
        if (status.auth_required) {
          const auth = await fetchAuth();
          if (cancelled) return;
          if (!auth.authenticated) {
            setLocked(true);
            return;
          }
        }
        await hydrateSession(true);
      } catch (err) {
        if (!cancelled) setError(friendlyDeskError(err instanceof Error ? err.message : String(err)));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function unlock(event: FormEvent) {
    event.preventDefault();
    if (!accessToken.trim()) return;
    setError(null);
    try {
      await loginDesk(accessToken.trim());
      setLocked(false);
      setAccessToken("");
      await hydrateSession(true);
    } catch (err) {
      setError(friendlyDeskError(err instanceof Error ? err.message : String(err)));
    }
  }

  const artifactList = useMemo(() => Object.values(artifacts), [artifacts]);

  async function send() {
    if (!sessionId || busy || !draft.trim()) return;
    const text = draft.trim();
    setDraft("");
    setError(null);
    const user: ChatMessage = { id: crypto.randomUUID(), role: "user", content: text, progress: [] };
    const assistantId = crypto.randomUUID();
    assistantIdRef.current = assistantId;
    const assistant: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      progress: [],
      reasoning: "",
      streaming: true,
    };
    setMessages((prev) => [...prev, user, assistant]);
    setBusy(true);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await streamMessage(
        sessionId,
        text,
        (event) => applyEvent(assistantId, event, setMessages, setArtifacts, setDisplay),
        controller.signal,
      );
    } catch (err) {
      if (!isAbort(err)) {
        setError(friendlyDeskError(err instanceof Error ? err.message : String(err)));
      }
    } finally {
      abortRef.current = null;
      assistantIdRef.current = null;
      setBusy(false);
      setMessages((prev) =>
        prev.map((item) => (item.id === assistantId ? { ...item, streaming: false } : item)),
      );
    }
  }

  async function stop() {
    if (sessionId) {
      try {
        await stopSession(sessionId);
      } catch {
        /* session may already be idle */
      }
    }
    abortRef.current?.abort();
    const assistantId = assistantIdRef.current;
    if (assistantId) {
      setMessages((prev) =>
        prev.map((item) =>
          item.id === assistantId
            ? {
                ...item,
                streaming: false,
                stopped: true,
                content: item.content || "Run stopped.",
              }
            : item,
        ),
      );
    }
    setBusy(false);
  }

  async function reset() {
    if (busy) await stop();
    setError(null);
    try {
      const created = await createSession(false);
      setSessionId(created.session_id);
      setMessages([]);
      setArtifacts({});
      setDisplay({ showReport: false, turn: 0, activeReportId: null });
      setDraft(STARTER_DRAFT);
    } catch (err) {
      setError(friendlyDeskError(err instanceof Error ? err.message : String(err)));
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          FREIGHT SB <small>RESEARCH DESK</small>
        </div>
        <div className="top-meta">
          <button
            type="button"
            className={`guide-toggle${guideOpen ? " on" : ""}`}
            onClick={() => setGuide(!guideOpen)}
            aria-expanded={guideOpen}
            aria-controls="desk-guide"
          >
            {guideOpen ? "Hide guide" : "Open guide"}
          </button>
          <span className={`pill ${busy ? "busy" : "live"}`}>{busy ? "running" : "live"}</span>
          <span className="mono">{health?.model ?? "connecting"}</span>
        </div>
      </header>
      {locked ? (
        <div className="unlock">
          <form className="unlock-card" onSubmit={unlock}>
            <h1>Desk locked</h1>
            <p>Enter the access token set as <code>DESK_ACCESS_TOKEN</code> on the host.</p>
            <input
              type="password"
              autoComplete="current-password"
              value={accessToken}
              onChange={(event) => setAccessToken(event.target.value)}
              placeholder="Access token"
              aria-label="Access token"
            />
            {error ? <div className="error">{error}</div> : null}
            <button type="submit" disabled={!accessToken.trim()}>
              Unlock
            </button>
          </form>
        </div>
      ) : guideOpen ? (
        <GuidePanel onHide={() => setGuide(false)} />
      ) : (
        <div className="workspace">
          <ChatPane
            messages={messages}
            draft={draft}
            busy={busy}
            error={error}
            showReasoning={showReasoning}
            onDraft={setDraft}
            onSend={send}
            onStop={stop}
            onReset={reset}
            onToggleReasoning={() => setShowReasoning((value) => !value)}
          />
          <Board artifacts={artifactList} display={display} />
        </div>
      )}
    </div>
  );
}

function isAbort(err: unknown) {
  return (
    (err instanceof DOMException && err.name === "AbortError") ||
    (err instanceof Error && err.name === "AbortError")
  );
}

function applyEvent(
  assistantId: string,
  event: DeskEvent,
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>,
  setArtifacts: Dispatch<SetStateAction<Record<string, Artifact>>>,
  setDisplay: Dispatch<SetStateAction<BoardDisplay>>,
) {
  if (event.type === "run_start") {
    const turn = Number(event.turn ?? 0);
    setDisplay((prev) => ({ ...prev, turn }));
  }
  if (event.type === "progress") {
    const incoming: Progress = {
      id: String(event.id),
      label: String(event.label),
      status: event.status === "done" ? "done" : "running",
    };
    setMessages((prev) =>
      prev.map((item) =>
        item.id === assistantId ? { ...item, progress: upsertProgress(item.progress, incoming) } : item,
      ),
    );
  }
  if (event.type === "reasoning") {
    const delta = String(event.delta ?? event.content ?? "");
    if (!delta) return;
    setMessages((prev) =>
      prev.map((item) =>
        item.id === assistantId ? { ...item, reasoning: `${item.reasoning || ""}${delta}` } : item,
      ),
    );
  }
  if (event.type === "message") {
    const content = String(event.content ?? "");
    setMessages((prev) =>
      prev.map((item) => (item.id === assistantId ? { ...item, content, streaming: false } : item)),
    );
  }
  if (event.type === "stopped") {
    const content = String(event.message ?? "Run stopped.");
    setMessages((prev) =>
      prev.map((item) =>
        item.id === assistantId
          ? { ...item, content: item.content || content, streaming: false, stopped: true }
          : item,
      ),
    );
  }
  if (event.type === "artifact") {
    const artifact = event.artifact as Artifact;
    if (artifact?.id) {
      setArtifacts((prev) => ({ ...prev, [artifact.id]: artifact }));
    }
  }
  if (event.type === "remove") {
    const id = String(event.id ?? "");
    if (id) {
      setArtifacts((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    }
  }
  if (event.type === "display") {
    setDisplay((prev) => ({
      ...prev,
      showReport: event.show_report !== undefined ? Boolean(event.show_report) : prev.showReport,
      activeReportId:
        event.active_report_id !== undefined ? (event.active_report_id as string | null) : prev.activeReportId,
    }));
  }
  if (event.type === "error") {
    const message = friendlyDeskError(String(event.message ?? "The run failed."));
    setMessages((prev) =>
      prev.map((item) =>
        item.id === assistantId
          ? { ...item, content: item.content || message, streaming: false }
          : item,
      ),
    );
  }
}

function upsertProgress(items: Progress[], incoming: Progress) {
  const idx = items.findIndex((item) => item.id === incoming.id);
  if (idx === -1) return [...items, incoming];
  const copy = [...items];
  copy[idx] = incoming;
  return copy;
}
