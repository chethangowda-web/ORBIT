import { describe, expect, it } from "vitest";
import { parseSseChunk } from "@/lib/live";

describe("parseSseChunk", () => {
  it("parses complete events and keeps the unfinished remainder", () => {
    const first = 'retry: 3000\n\nevent: change\ndata: {"topic":"tasks","task_id":"a"}\n\nevent: change\ndata: {"top';
    const { events, rest } = parseSseChunk(first);
    expect(events).toEqual([{ topic: "tasks", task_id: "a" }]);
    const next = parseSseChunk(rest + 'ic":"comments","task_id":"b"}\n\n');
    expect(next.events).toEqual([{ topic: "comments", task_id: "b" }]);
    expect(next.rest).toBe("");
  });

  it("ignores keep-alive comments and malformed frames without throwing", () => {
    const { events } = parseSseChunk(': keep-alive\n\nevent: change\ndata: not-json\n\nevent: change\ndata: {"topic":"resync","task_id":null}\n\n');
    expect(events).toEqual([{ topic: "resync", task_id: null }]);
  });
});
