export interface NavigationBenchmark {
  kind: "oma_navigation_benchmark_v1";
  created_at: string;
  status: "COMPLETED" | "CANCELLED";
  reason?: string;
  project_id: string | null;
  state_root?: string;
  scene: {
    objects: number;
    triangles: number;
    draw_calls: number;
    width: number;
    height: number;
    drawing_buffer_width?: number;
    drawing_buffer_height?: number;
    pixel_ratio: number;
    clipped: boolean;
    xray: boolean;
    comparison: boolean;
  };
  renderer: { vendor: string; renderer: string; browser: string };
  protocol: {
    warmup_ms: number;
    measurement_ms: number;
    path: string;
    frame_cost: string;
  };
  frames: number;
  elapsed_ms: number;
  average_fps: number;
  frame_interval_p50_ms: number;
  frame_interval_p95_ms: number;
  cpu_submission_p95_ms: number;
  gpu_timer_status?:
    "AVAILABLE" | "UNAVAILABLE" | "DISABLED" | "DISJOINT" | "NO_SAMPLES";
  gpu_frame_p95_ms?: number;
  gpu_samples?: number;
  frames_over_33_33ms: number;
  average_30fps_gate: "PASS" | "FAIL" | "NOT_EVALUATED";
  scheduling?: SchedulingEvidence;
}
export interface SchedulingEvidence {
  timer_requested_ms: number;
  timer_samples: number;
  timer_interval_p50_ms: number;
  timer_interval_p95_ms: number;
  timer_interval_max_ms: number;
  timer_intervals_ms: number[];
  start: { visibility: DocumentVisibilityState; focused: boolean };
  end: { visibility: DocumentVisibilityState; focused: boolean };
  context_changes: {
    elapsed_ms: number;
    visibility: DocumentVisibilityState;
    focused: boolean;
  }[];
}

/** Independent timer samples expose scheduling context; they do not replace RAF measurements. */
export function startSchedulingProbe(warmupMs = 2000) {
  const context = () => ({
    visibility: document.visibilityState,
    focused: document.hasFocus(),
  });
  const start = context(),
    started = performance.now();
  let previous = started,
    previousContext = start,
    stopped = false;
  const intervals: number[] = [],
    changes: SchedulingEvidence["context_changes"] = [];
  let timer: ReturnType<typeof setTimeout>;
  const tick = () => {
    if (stopped) return;
    const now = performance.now(),
      current = context();
    if (now - started >= warmupMs) intervals.push(now - previous);
    if (
      current.visibility !== previousContext.visibility ||
      current.focused !== previousContext.focused
    ) {
      changes.push({ elapsed_ms: now - started, ...current });
      previousContext = current;
    }
    previous = now;
    timer = setTimeout(tick, 100);
  };
  timer = setTimeout(tick, 100);
  return () => {
    stopped = true;
    clearTimeout(timer);
    return {
      timer_requested_ms: 100,
      timer_samples: intervals.length,
      timer_interval_p50_ms: percentile(intervals, 0.5),
      timer_interval_p95_ms: percentile(intervals, 0.95),
      timer_interval_max_ms: Math.max(0, ...intervals),
      timer_intervals_ms: [...intervals],
      start,
      end: context(),
      context_changes: [...changes],
    } satisfies SchedulingEvidence;
  };
}
export function percentile(values: number[], quantile: number) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[
    Math.min(
      sorted.length - 1,
      Math.max(0, Math.ceil(quantile * sorted.length) - 1),
    )
  ];
}
export function downloadJson(value: unknown, name: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
