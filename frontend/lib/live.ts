"use client";

/**
 * Live updates over Server-Sent Events.
 *
 * The server only says "something changed"; this hook then invalidates the relevant TanStack
 * queries so data is refetched through the normal, authorised REST API. `fetch` is used instead
 * of EventSource because EventSource cannot send the Authorization header.
 * Polling stays on as a fallback, so a dropped stream degrades to slower updates, never to stale data.
 */

import { useEffect, useState } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { API_BASE_URL, TOKEN_KEY } from "./api-client";
import { keys } from "./hooks";

export interface LiveEvent {
  topic: string;
  task_id: string | null;
}

/** Splits a streamed buffer into complete events plus the unfinished remainder. */
export function parseSseChunk(buffer: string): { events: LiveEvent[]; rest: string } {
  const frames = buffer.split("\n\n");
  const rest = frames.pop() ?? "";
  const events: LiveEvent[] = [];
  for (const frame of frames) {
    const data = frame
      .split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trim())
      .join("");
    if (!data) continue; // retry hints and ": keep-alive" comments
    try {
      const parsed = JSON.parse(data) as LiveEvent;
      if (typeof parsed.topic === "string") events.push(parsed);
    } catch {
      /* ignore a malformed frame rather than dropping the connection */
    }
  }
  return { events, rest };
}

export function invalidateForEvents(queryClient: QueryClient) {
  queryClient.invalidateQueries({ queryKey: keys.tasks });
  queryClient.invalidateQueries({ queryKey: keys.stats });
  queryClient.invalidateQueries({ queryKey: keys.workload });
  queryClient.invalidateQueries({ queryKey: keys.week });
}

const MIN_BACKOFF_MS = 1_000;
const MAX_BACKOFF_MS = 30_000;
const DEBOUNCE_MS = 250;

export function useLiveUpdates(enabled = true): boolean {
  const queryClient = useQueryClient();
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let backoff = MIN_BACKOFF_MS;

    const schedule = () => {
      clearTimeout(timer);
      timer = setTimeout(() => invalidateForEvents(queryClient), DEBOUNCE_MS);
    };

    const connect = async () => {
      const token = window.localStorage.getItem(TOKEN_KEY);
      if (!token) return;
      try {
        const res = await fetch(`${API_BASE_URL}/events/stream`, {
          headers: { Authorization: `Bearer ${token}`, Accept: "text/event-stream" },
          signal: controller.signal,
          cache: "no-store",
        });
        if (res.status === 401) return; // session ended; the auth handler takes over
        if (!res.ok || !res.body) throw new Error(`stream status ${res.status}`);

        setConnected(true);
        if (backoff !== MIN_BACKOFF_MS) schedule(); // catch up on whatever was missed while offline
        backoff = MIN_BACKOFF_MS;

        const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
        let buffer = "";
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += value;
          const { events, rest } = parseSseChunk(buffer);
          buffer = rest;
          if (events.length) schedule();
        }
      } catch {
        /* fall through to reconnect */
      }
      setConnected(false);
      if (controller.signal.aborted) return;
      retry = setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, MAX_BACKOFF_MS);
    };

    connect();
    return () => {
      controller.abort();
      clearTimeout(timer);
      clearTimeout(retry);
      setConnected(false);
    };
  }, [enabled, queryClient]);

  return connected;
}
