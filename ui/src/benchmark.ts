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
  gpu_timer_status?: "AVAILABLE" | "UNAVAILABLE" | "DISJOINT" | "NO_SAMPLES";
  gpu_frame_p95_ms?: number;
  gpu_samples?: number;
  frames_over_33_33ms: number;
  average_30fps_gate: "PASS" | "FAIL" | "NOT_EVALUATED";
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
