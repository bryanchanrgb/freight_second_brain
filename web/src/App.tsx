import { useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from "react";
import Board from "./components/Board";
import ChatPane from "./components/ChatPane";
import { createSession, fetchHealth, stopSession, streamMessage } from "./api";
import type { Artifact, BoardDisplay, ChatMessage, DeskEvent, Progress } from "./types";

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [health, setHealth] = useState<{ model: string; exa_backend: string } | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [artifacts, setArtifacts] = useState<Record<string, Artifact>>({});
  const [display, setDisplay] = useState<BoardDisplay>({ showReport: false, turn: 0 });
  const [draft, setDraft] = useState(
    "As of today, horizon session/week: what is the latest Baltic Dry Index print, and how did Capesize and Panamax split?",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showReasoning, setShowReasoning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const assistantIdRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [created, status] = await Promise.all([createSession(), fetchHealth()]);
        if (cancelled) return;
        setSessionId(created.session_id);
        setHealth({ model: status.model, exa_backend: status.exa_backend });
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

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
        setError(err instanceof Error ? err.message : String(err));
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

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          FREIGHT SB <small>RESEARCH DESK</small>
        </div>
        <div className="top-meta">
          <span className={`pill ${busy ? "busy" : "live"}`}>{busy ? "running" : "live"}</span>
          <span className="mono">{health?.model ?? "connecting"}</span>
        </div>
      </header>
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
          onToggleReasoning={() => setShowReasoning((value) => !value)}
        />
        <Board artifacts={artifactList} display={display} />
      </div>
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
    }));
  }
  if (event.type === "error") {
    setMessages((prev) =>
      prev.map((item) =>
        item.id === assistantId
          ? { ...item, content: item.content || String(event.message ?? "The run failed."), streaming: false }
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
