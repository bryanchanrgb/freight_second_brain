import type { DeskEvent } from "./types";

async function readJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export async function createSession() {
  return readJson<{ session_id: string; title: string }>(
    await fetch("/api/sessions", { method: "POST" }),
  );
}

export async function fetchHealth() {
  return readJson<{ ok: boolean; model: string; exa_backend: string }>(await fetch("/api/health"));
}

export async function stopSession(sessionId: string) {
  return readJson<{ ok: boolean; stopped?: boolean }>(
    await fetch(`/api/sessions/${sessionId}/stop`, { method: "POST" }),
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
  });
  if (!res.ok || !res.body) {
    throw new Error((await res.text()) || res.statusText);
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
