import { readMeshStream, type MeshProgress } from "./meshStream";
import {
  recordTiming,
  startControl,
  acknowledgeControl,
  failedControl,
} from "./telemetry";
import type {
  EngineEvent,
  Snapshot,
  Project,
  Geometry,
  Health,
  RunRequest,
  Run,
  AssuranceRecord,
  DependencyRecord,
  OpeningHostInspection,
} from "./types";
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function request<T>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const started = performance.now();
  const response = await fetch(`/api${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  const content = await response.text();
  let result: unknown;
  try {
    result = content ? JSON.parse(content) : {};
  } catch {
    throw new ApiError(
      response.status,
      "The local engine returned an unreadable response. Check the service diagnostics.",
    );
  }
  if (!response.ok) {
    const data = result as Record<string, unknown>;
    throw new ApiError(
      response.status,
      typeof data.detail === "string"
        ? data.detail
        : typeof data.error === "string"
          ? data.error
          : JSON.stringify(data.detail ?? data),
    );
  }
  recordTiming("api_response", {
    path,
    method: body === undefined ? "GET" : "POST",
    status: response.status,
    elapsed_ms: performance.now() - started,
  });
  return result as T;
}
const p = (id: string) => `/projects/${encodeURIComponent(id)}`;
export type StateSelection = { revision?: number; candidate_id?: string };
export function selectionQuery(selection?: StateSelection) {
  if (!selection) return "";
  const params = new URLSearchParams();
  if (selection.revision !== undefined)
    params.set("revision", String(selection.revision));
  if (selection.candidate_id)
    params.set("candidate_id", selection.candidate_id);
  return `?${params}`;
}
const mutationKeys = new Map<string, string>();
const snapshotSizes = new Map<string, number>();
async function creation<T>(
  intent: string,
  path: string,
  body: Record<string, unknown>,
): Promise<T> {
  const key = mutationKey(intent);
  const result = await request<T>(path, { ...body, idempotency_key: key });
  mutationKeys.delete(intent);
  return result;
}
export function mutationKey(intent: string) {
  let key = mutationKeys.get(intent);
  if (!key) {
    key = crypto.randomUUID();
    mutationKeys.set(intent, key);
    if (mutationKeys.size > 500)
      mutationKeys.delete(mutationKeys.keys().next().value!);
  }
  return key;
}
export const api = {
  openingHost: (
    id: string,
    entityId: string,
    revision: number,
    signal?: AbortSignal,
  ) =>
    request<OpeningHostInspection>(
      `${p(id)}/opening-host?${new URLSearchParams({ entity_id: entityId, revision: String(revision) })}`,
      undefined,
      signal,
    ),
  health: () => request<Health>("/health"),
  projects: async () => {
    const r = await request<Project[] | { projects: Project[] }>("/projects");
    return Array.isArray(r) ? r : r.projects;
  },
  snapshot: async (
    id: string,
    signal?: AbortSignal,
    selection?: StateSelection,
  ) => {
    const data = await request<Snapshot>(
      `${p(id)}/snapshot${selectionQuery(selection)}`,
      undefined,
      signal,
    );
    snapshotSizes.set(
      `${id}:${selectionQuery(selection)}`,
      data.entities.length,
    );
    snapshotSizes.set(
      `${id}:${selectionQuery({ revision: data.project.revision })}`,
      data.entities.length,
    );
    return data;
  },
  geometry: async (
    id: string,
    signal?: AbortSignal,
    selection?: StateSelection,
    onProgress?: (progress: MeshProgress) => void,
  ) => {
    const path = `${p(id)}/geometry-stream${selectionQuery(selection)}`,
      started = performance.now();
    const response = await fetch(`/api${path}`, { signal });
    if (response.status === 404) {
      if (
        (snapshotSizes.get(`${id}:${selectionQuery(selection)}`) ?? Infinity) >
        20000
      )
        throw new Error(
          "This large federation requires the streamed geometry endpoint. Restart the updated local engine and reconnect.",
        );
      return request<Geometry>(
        `${p(id)}/geometry${selectionQuery(selection)}`,
        undefined,
        signal,
      );
    }
    if (!response.ok)
      throw new ApiError(
        response.status,
        `Geometry stream returned HTTP ${response.status}`,
      );
    const result = await readMeshStream(response, onProgress);
    recordTiming("geometry_stream_complete", {
      path,
      elapsed_ms: performance.now() - started,
      mesh_count: result.meshes.length,
      state_root: result.state_root,
    });
    return result;
  },
  events: async (id: string, after: number) => {
    const r = await request<EngineEvent[] | { events: EngineEvent[] }>(
      `${p(id)}/events?after=${after}&limit=500`,
    );
    return Array.isArray(r) ? r : r.events;
  },
  import: (paths: string[], name: string) =>
    creation<Project | { project: Project }>(
      `import:${name}:${JSON.stringify(paths)}`,
      "/projects/import",
      { paths, name },
    ),
  start: (id: string, run: RunRequest) =>
    creation<Run>(`start:${id}:${JSON.stringify(run)}`, `${p(id)}/runs`, {
      ...run,
    }),
  recheck: (id: string, candidate: string, budget_seconds = 300) =>
    creation<Run>(
      `recheck:${id}:${candidate}:${budget_seconds}`,
      `${p(id)}/candidates/${encodeURIComponent(candidate)}/recheck`,
      { budget_seconds },
    ),
  assurance: async (
    id: string,
    candidate: string,
    root: string,
    signal?: AbortSignal,
  ) => {
    const data = await request<AssuranceRecord>(
      `${p(id)}/candidates/${encodeURIComponent(candidate)}/assurance`,
      undefined,
      signal,
    );
    if (data.candidate_id !== candidate || data.candidate_root !== root)
      throw new Error(
        "Assurance belongs to a different candidate or state root. Reload this view.",
      );
    return data;
  },
  dependencies: async (
    id: string,
    selection: StateSelection,
    root: string,
    signal?: AbortSignal,
  ) => {
    const data = await request<DependencyRecord>(
      `${p(id)}/dependencies${selectionQuery(selection)}`,
      undefined,
      signal,
    );
    if (data.after_root !== root)
      throw new Error(
        "Dependency evidence belongs to a different state root. Reload this view.",
      );
    return data;
  },
  control: async (id: string, action: string) => {
    startControl(id, action);
    try {
      const result = await request<Run>(
        `/runs/${encodeURIComponent(id)}/control`,
        { action },
      );
      acknowledgeControl(id, result.status);
      return result;
    } catch (error) {
      failedControl(id, (error as Error).message);
      throw error;
    }
  },
  accept: (id: string, candidate: string, revision: number) =>
    request(`${p(id)}/candidates/${encodeURIComponent(candidate)}/accept`, {
      expected_revision: revision,
      idempotency_key: mutationKey(`accept:${id}:${candidate}:${revision}`),
    }),
  revert: (id: string, revision: number, current: number) =>
    request(`${p(id)}/revert`, {
      revision,
      expected_revision: current,
      idempotency_key: mutationKey(`revert:${id}:${revision}:${current}`),
    }),
  export: (id: string, candidate_id?: string, draft = true) =>
    request<Record<string, unknown>>(`${p(id)}/export`, {
      candidate_id,
      draft,
    }),
};
export function mergeEvents(
  current: EngineEvent[],
  incoming: EngineEvent[],
  projectId: string,
  limit = 2000,
): EngineEvent[] {
  const map = new Map(
    current.filter((e) => e.project_id === projectId).map((e) => [e.seq, e]),
  );
  for (const event of incoming)
    if (
      event.project_id === projectId &&
      Number.isSafeInteger(event.seq) &&
      event.seq > 0 &&
      !map.has(event.seq)
    )
      map.set(event.seq, event);
  return [...map.values()].sort((a, b) => a.seq - b.seq).slice(-limit);
}
export function eventCursor(events: EngineEvent[], previous = 0) {
  return events.reduce((n, e) => Math.max(n, e.seq), previous);
}
export function normalizeSnapshot(s: Snapshot): Snapshot {
  return {
    ...s,
    entities: s.entities ?? [],
    sources: s.sources ?? [],
    issues: s.issues ?? [],
    checks: s.checks ?? [],
    candidates: s.candidates ?? [],
    runs: s.runs ?? [],
    history: s.history ?? [],
    constraints: s.constraints ?? [],
    missing_inputs: s.missing_inputs ?? [],
  };
}
