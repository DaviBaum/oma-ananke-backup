import { afterEach, describe, expect, it, vi } from "vitest";
import { startSchedulingProbe } from "./benchmark";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("independent scheduling evidence", () => {
  it("records actual elapsed timer intervals after warmup and stops scheduling", () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "performance"] });
    const state = { visibilityState: "visible", hasFocus: () => false };
    vi.stubGlobal("document", state);
    const stop = startSchedulingProbe(200);
    vi.advanceTimersByTime(350);
    const result = stop();
    expect(result.timer_intervals_ms).toEqual([100, 100]);
    expect(result.timer_samples).toBe(2);
    expect(result.timer_interval_p95_ms).toBe(100);
    expect(result.start).toEqual({ visibility: "visible", focused: false });
    expect(vi.getTimerCount()).toBe(0);
  });

  it("retains a focus/visibility change without assigning a cause or a performance verdict", () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "performance"] });
    let focused = true;
    const state = { visibilityState: "visible", hasFocus: () => focused };
    vi.stubGlobal("document", state);
    const stop = startSchedulingProbe();
    focused = false;
    state.visibilityState = "hidden";
    vi.advanceTimersByTime(100);
    const result = stop();
    expect(result.context_changes).toEqual([
      { elapsed_ms: 100, visibility: "hidden", focused: false },
    ]);
    expect(result.timer_samples).toBe(0);
    expect(result.end).toEqual({ visibility: "hidden", focused: false });
    expect(result).not.toHaveProperty("average_30fps_gate");
  });
});
