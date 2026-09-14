import { describe, it, expect, vi } from "vitest";
import {
  api,
  mergeEvents,
  eventCursor,
  selectionQuery,
  mutationKey,
} from "./api";
import type { EngineEvent } from "./types";
const event = (
  seq: number,
  project_id = "p",
  state_root = "old",
): EngineEvent => ({
  seq,
  project_id,
  state_root,
  timestamp: "2026-09-14T00:00:00Z",
  stage: "check",
  status: "RUNNING",
});
describe("durable event reconciliation", () => {
  it("rejects assurance for another candidate even when its root matches", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({
              candidate_id: "other",
              candidate_root: "root",
              support_status: "SUPPORTED_CONDITIONALLY",
            }),
          ),
        ),
    );
    try {
      await expect(
        api.assurance("project", "selected", "root"),
      ).rejects.toThrow("different candidate or state root");
    } finally {
      vi.unstubAllGlobals();
    }
  });
  it("pins dependency revision zero and rejects a stale response root", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify({ after_root: "previous-root" })),
      );
    vi.stubGlobal("fetch", fetcher);
    try {
      await expect(
        api.dependencies("project", { revision: 0 }, "selected-root"),
      ).rejects.toThrow("different state root");
      expect(fetcher.mock.calls[0][0]).toBe(
        "/api/projects/project/dependencies?revision=0",
      );
    } finally {
      vi.unstubAllGlobals();
    }
  });
  it("retains one recheck identity across an uncertain retry", async () => {
    const fetcher = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Connection lost"))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "rechecked", status: "QUEUED" }), {
          status: 202,
        }),
      );
    vi.stubGlobal("fetch", fetcher);
    try {
      await expect(
        api.recheck("p-recheck", "candidate-a", 300),
      ).rejects.toThrow("Connection lost");
      await api.recheck("p-recheck", "candidate-a", 300);
      expect(fetcher.mock.calls[0][0]).toBe(
        "/api/projects/p-recheck/candidates/candidate-a/recheck",
      );
      const bodies = fetcher.mock.calls.map((c) => JSON.parse(c[1].body));
      expect(bodies[0]).toEqual(bodies[1]);
      expect(bodies[0].budget_seconds).toBe(300);
    } finally {
      vi.unstubAllGlobals();
    }
  });
  it("retries an uncertain run creation with the same key, then gives a new explicit run a new identity", async () => {
    const fetcher = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Connection lost"))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "confirmed", status: "QUEUED" }), {
          status: 202,
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "new-run", status: "QUEUED" }), {
          status: 202,
        }),
      );
    vi.stubGlobal("fetch", fetcher);
    try {
      await expect(
        api.start("retry-project", { operation: "check" }),
      ).rejects.toThrow("Connection lost");
      await api.start("retry-project", { operation: "check" });
      await api.start("retry-project", { operation: "check" });
      const keys = fetcher.mock.calls.map(
        (call) => JSON.parse(call[1].body).idempotency_key,
      );
      expect(keys[0]).toBe(keys[1]);
      expect(keys[2]).not.toBe(keys[1]);
    } finally {
      vi.unstubAllGlobals();
    }
  });
  it("retains revision zero in historical snapshot selection", () =>
    expect(selectionQuery({ revision: 0 })).toBe("?revision=0"));
  it("reuses idempotency identities for retries of the same mutation intent", () => {
    expect(mutationKey("accept:p:c:1")).toBe(mutationKey("accept:p:c:1"));
    expect(mutationKey("accept:p:c:2")).not.toBe(mutationKey("accept:p:c:1"));
  });
  it("sorts reconnect catch-up and suppresses duplicate publication", () =>
    expect(
      mergeEvents([event(2)], [event(3), event(1), event(2)], "p").map(
        (e) => e.seq,
      ),
    ).toEqual([1, 2, 3]));
  it("rejects events from previously selected project", () =>
    expect(
      mergeEvents([event(2, "old")], [event(9, "old"), event(1)], "p").map(
        (e) => e.seq,
      ),
    ).toEqual([1]));
  it("cannot overwrite an already observed immutable event", () =>
    expect(
      mergeEvents(
        [event(1, "p", "original")],
        [event(1, "p", "changed")],
        "p",
      )[0].state_root,
    ).toBe("original"));
  it("bounds memory while preserving monotonic cursor", () => {
    const result = mergeEvents(
      [],
      Array.from({ length: 20 }, (_, i) => event(20 - i)),
      "p",
      5,
    );
    expect(result.map((e) => e.seq)).toEqual([16, 17, 18, 19, 20]);
    expect(eventCursor(result, 25)).toBe(25);
  });
  it("rejects invalid sequence numbers", () =>
    expect(
      mergeEvents([], [event(-1), event(NaN), event(1.5), event(0)], "p"),
    ).toEqual([]));
});
