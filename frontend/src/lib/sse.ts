import { useEffect, useRef } from "react";
import { sseUrl } from "./api";

export interface SSEEvent {
  type: string;
  data: Record<string, unknown>;
}

export function useProjectSSE(projectId: number | null, onEvent: (ev: SSEEvent) => void) {
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;

  useEffect(() => {
    if (!projectId) return;
    let es: EventSource | null = null;
    let retryMs = 2000;

    const connect = () => {
      es = new EventSource(sseUrl(projectId));
      es.onmessage = (e) => {
        handlerRef.current({ type: "message", data: JSON.parse(e.data || "{}") });
      };
      es.onopen = () => {
        retryMs = 2000;
      };
      es.onerror = () => {
        es?.close();
        retryMs = Math.min(retryMs * 2, 30000);
        setTimeout(() => {
          if (!es) connect();
        }, retryMs);
      };
    };
    connect();
    return () => {
      es?.close();
      es = null;
    };
  }, [projectId]);
}

export function parseEventLine(raw: string): SSEEvent | null {
  const lines = raw.split("\n");
  let type = "message";
  let data = "";
  for (const line of lines) {
    if (line.startsWith("event:")) type = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return null;
  try {
    return { type, data: JSON.parse(data) };
  } catch {
    return { type, data: { raw: data } };
  }
}
