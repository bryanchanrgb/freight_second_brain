import { useEffect, useMemo, useRef, useState, type Dispatch, type FormEvent, type SetStateAction } from "react";
import Board from "./components/Board";
import ChatPane from "./components/ChatPane";
import GuidePanel from "./components/GuidePanel";
import { createSession, fetchAuth, fetchHealth, loginDesk, stopSession, streamMessage } from "./api";
import { friendlyDeskError } from "./errors";
import type { Artifact, BoardDisplay, ChatMessage, DeskEvent, Progress } from "./types";
import { MOBILE_QUERY, useMediaQuery } from "./useMediaQuery";

const GUIDE_KEY = "freight-sb-guide-open";
const STARTER_DRAFT = "What recent events are impacting Panamax demand?";

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
  const [reportOpen, setReportOpen] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const assistantIdRef = useRef<string | null>(null);
  const isMobile = useMediaQuery(MOBILE_QUERY);

  function setGuide(open: boolean) {
    setGuideOpen(open);
    if (open) setReportOpen(false);
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
        if (status.openrouter_key === false) {
          setError(
            "Language model unavailable: the OpenRouter key is missing or invalid.",
          );
          return;
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
  const hasReport = artifactList.some((item) => item.kind === "report");

  useEffect(() => {
    if (!isMobile) setReportOpen(false);
  }, [isMobile]);

  useEffect(() => {
    if (!isMobile || !reportOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setReportOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isMobile, reportOpen]);

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
      setReportOpen(false);
      setDraft(STARTER_DRAFT);
    } catch (err) {
      setError(friendlyDeskError(err instanceof Error ? err.message : String(err)));
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          Freight Second Brain <small>RESEARCH DESK</small>
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
            <h1>This desk is private</h1>
            <p>Enter the password to open the research desk.</p>
            <input
              type="password"
              autoComplete="current-password"
              value={accessToken}
              onChange={(event) => setAccessToken(event.target.value)}
              placeholder="Password"
              aria-label="Desk password"
            />
            {error ? <div className="error">{error}</div> : null}
            <button type="submit" disabled={!accessToken.trim()}>
              Continue
            </button>
          </form>
        </div>
      ) : guideOpen ? (
        <GuidePanel onHide={() => setGuide(false)} />
      ) : (
        <div className={`workspace${isMobile && reportOpen ? " report-overlay-open" : ""}`}>
          <ChatPane
            messages={messages}
            draft={draft}
            busy={busy}
            error={error}
            showReasoning={showReasoning}
            hasReport={hasReport}
            onDraft={setDraft}
            onSend={send}
            onStop={stop}
            onReset={reset}
            onToggleReasoning={() => setShowReasoning((value) => !value)}
            onOpenReport={isMobile && hasReport ? () => setReportOpen(true) : undefined}
          />
          <Board
            artifacts={artifactList}
            display={display}
            onClose={isMobile && reportOpen ? () => setReportOpen(false) : undefined}
          />
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
    const message = friendlyDeskError(String(event.message ?? "Something went wrong."));
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
