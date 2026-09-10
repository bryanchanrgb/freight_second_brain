import { friendlyDeskError } from "./errors";
import type { Artifact, BoardDisplay, ChatMessage, DeskEvent } from "./types";

async function readJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(friendlyDeskError(text || res.statusText));
  }
  return res.json() as Promise<T>;
}

const FETCH_INIT: RequestInit = { credentials: "include" };

export type SessionPayload = {
  session_id: string;
  title: string;
  preloaded?: boolean;
  messages?: ChatMessage[];
  artifacts?: Artifact[];
  display?: BoardDisplay;
};

export type HealthPayload = {
  ok: boolean;
  model: string;
  exa_backend: string;
  auth_required?: boolean;
};

export type AuthPayload = {
  ok: boolean;
  auth_required: boolean;
  authenticated: boolean;
};

export async function createSession(preload = false) {
  const query = preload ? "?preload=true" : "";
  return readJson<SessionPayload>(
    await fetch(`/api/sessions${query}`, { method: "POST", ...FETCH_INIT }),
  );
}

export async function fetchHealth() {
  return readJson<HealthPayload>(await fetch("/api/health", FETCH_INIT));
}

export async function fetchAuth() {
  return readJson<AuthPayload>(await fetch("/api/auth", FETCH_INIT));
}

export async function loginDesk(token: string) {
  return readJson<AuthPayload>(
    await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
      ...FETCH_INIT,
    }),
  );
}

export async function logoutDesk() {
  return readJson<AuthPayload>(
    await fetch("/api/logout", { method: "POST", ...FETCH_INIT }),
  );
}

export async function stopSession(sessionId: string) {
  return readJson<{ ok: boolean; stopped?: boolean }>(
    await fetch(`/api/sessions/${sessionId}/stop`, { method: "POST", ...FETCH_INIT }),
  );
}

export async function streamMessage(
  sessionId: string,
  content: string,
  onEvent: (event: DeskEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`/api/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
    signal,
    ...FETCH_INIT,
  });
  if (!res.ok || !res.body) {
    throw new Error(friendlyDeskError((await res.text()) || res.statusText));
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const line = chunk
        .split("\n")
        .filter((row) => row.startsWith("data:"))
        .map((row) => row.slice(5).trim())
        .join("");
      if (!line) continue;
      onEvent(JSON.parse(line) as DeskEvent);
    }
  }
}
