export interface TimingRecord {
  kind: string;
  observed_at: string;
  elapsed_ms?: number;
  [key: string]: unknown;
}
const records: TimingRecord[] = [];
const pending = new Map<
  string,
  {
    action: string;
    start: number;
    ack_status?: string;
    requestRendered?: boolean;
    runningObserved?: boolean;
  }
>();
export function recordTiming(
  kind: string,
  detail: Record<string, unknown> = {},
) {
  records.push({ kind, observed_at: new Date().toISOString(), ...detail });
  if (records.length > 300) records.shift();
}
export function timingEvidence() {
  return {
    kind: "oma_browser_timings_v1",
    clock:
      "performance.now() for elapsed durations; timestamps are browser wall clock",
    records: [...records],
  };
}
export function startControl(id: string, action: string) {
  pending.set(id, { action, start: performance.now() });
}
export function acknowledgeControl(id: string, status: string) {
  const entry = pending.get(id);
  if (!entry) return;
  entry.ack_status = status;
  recordTiming("control_request_durable", {
    run_id: id,
    action: entry.action,
    status,
    elapsed_ms: performance.now() - entry.start,
  });
}
export function failedControl(id: string, reason: string) {
  const entry = pending.get(id);
  if (!entry) return;
  recordTiming("control_failed", {
    run_id: id,
    action: entry.action,
    reason,
    elapsed_ms: performance.now() - entry.start,
  });
  pending.delete(id);
}
export function observeControls(
  runs: { id: string; status: string; desired_action?: string }[],
) {
  for (const run of runs) {
    const entry = pending.get(run.id);
    if (!entry || !entry.ack_status) continue;
    const desired = entry.action === "resume" ? "run" : entry.action;
    if (!entry.requestRendered && run.desired_action === desired) {
      entry.requestRendered = true;
      recordTiming("control_request_rendered", {
        run_id: run.id,
        action: entry.action,
        desired_action: desired,
        status: run.status,
        elapsed_ms: performance.now() - entry.start,
      });
    }
    if (run.status === "RUNNING" || run.status === "CHECKING")
      entry.runningObserved = true;
    const expected =
      entry.action === "pause"
        ? "PAUSED"
        : entry.action === "resume"
          ? "RUNNING"
          : entry.action === "cancel"
            ? "CANCELLED"
            : entry.runningObserved
              ? "PAUSED"
              : undefined;
    if (
      run.status === expected ||
      /COMPLETED|FAILED|CRASHED|CANCELLED/.test(run.status)
    ) {
      recordTiming("control_state_rendered", {
        run_id: run.id,
        action: entry.action,
        status: run.status,
        expected_status: expected,
        achieved: run.status === expected,
        elapsed_ms: performance.now() - entry.start,
      });
      pending.delete(run.id);
    }
  }
}
