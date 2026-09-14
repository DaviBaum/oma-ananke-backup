export type Vec3 = [number, number, number];
export type Bounds = { min: Vec3; max: Vec3 };
export type Status =
  | "IMPORTED"
  | "BASELINE"
  | "CANDIDATE"
  | "CHECKING"
  | "CHECKED"
  | "ACCEPTED"
  | "REJECTED"
  | "STALE"
  | "UNKNOWN"
  | "PASS"
  | "FAIL"
  | "BLOCKED"
  | "RUNNING"
  | "PAUSED"
  | "CANCELLED"
  | "COMPLETED"
  | string;
export interface Entity {
  id: string;
  guid?: string;
  step_id?: number;
  name?: string;
  ifc_type?: string;
  source_file?: string;
  discipline?: string;
  storey?: string;
  system?: string;
  system_ids?: string[];
  geometry_status?: string;
  bounds?: Bounds;
  properties?: Record<string, unknown>;
  locked?: boolean;
  [key: string]: unknown;
}
export interface MeshData {
  entity_id: string;
  vertices: number[] | Float64Array;
  faces: number[] | Uint32Array;
  color?: [number, number, number];
  discipline?: string;
}
export interface Geometry {
  project_id: string;
  state_root: string;
  revision?: number;
  units: "m";
  coordinate_system?: string;
  meshes: MeshData[];
  bounds?: Bounds;
  truncated?: boolean;
  total_meshes?: number;
}
export interface Project {
  id: string;
  name: string;
  revision: number;
  state_root: string;
  current_revision?: number;
  current_state_root?: string;
  status: Status;
  created_at?: string;
  [key: string]: unknown;
}
export interface Issue {
  id: string;
  rule: string;
  status: Status;
  severity?: string;
  participants: string[];
  message: string;
  scope?: unknown;
  witness?: {
    point?: Vec3;
    other_point?: Vec3;
    margin_m?: number;
    required_clearance_m?: number;
    bounds?: Bounds;
  };
  artifact?: string;
}
export interface Route {
  id?: string;
  points?: Vec3[];
  points_m?: Vec3[];
  centerline?: Vec3[];
  radius_m?: number;
  radius?: number;
  diameter_m?: number;
  insulation_m?: number;
  clearance_m?: number;
  section?: {
    radius_m?: number;
    diameter_m?: number;
    insulation_m?: number;
    width_m?: number;
    height_m?: number;
  };
  [key: string]: unknown;
}
export interface Candidate {
  id: string;
  run_id?: string;
  state_root: string;
  status: Status;
  objective: Record<string, number>;
  check?: { status: Status; reason?: string; scope?: unknown };
  changed_ids: string[];
  created_at?: string;
  routes: Route[];
  [key: string]: unknown;
}
export interface Run {
  desired_action?: string;
  id: string;
  status: Status;
  stage?: string;
  operation?: string;
  created_at?: string;
  elapsed_seconds?: number;
  message?: string;
  candidate_ids?: string[];
  [key: string]: unknown;
}
export interface EngineEvent {
  seq: number;
  project_id: string;
  run_id?: string;
  branch_id?: string;
  state_root?: string;
  candidate_id?: string;
  timestamp: string;
  stage: string;
  status: Status;
  message?: string;
  changed_ids?: string[];
  artifacts?: unknown[];
  payload?: Record<string, unknown>;
}
export interface Revision {
  revision: number;
  state_root: string;
  status: Status;
  created_at?: string;
  timestamp?: string;
  message?: string;
  candidate_id?: string;
}
export interface CheckRecord {
  id: string;
  candidate_id: string;
  report_root: string;
  status: Status;
  reason: string;
  scope: string;
  participants: string[];
  witness?: Issue["witness"];
}
export interface Snapshot {
  project: Project;
  entities: Entity[];
  sources: Record<string, unknown>[];
  issues: Issue[];
  checks?: CheckRecord[];
  candidates: Candidate[];
  runs: Run[];
  history: Revision[];
  constraints: unknown[];
  missing_inputs: unknown[];
  events_seq?: number;
  [key: string]: unknown;
}
export interface Health {
  status: string;
  version?: string;
  hardware?: {
    cpu?: unknown;
    cpu_percent?: number;
    ram_total_bytes?: number;
    ram_available_bytes?: number;
    ram_used_bytes?: number;
    gpu?: {
      name?: string;
      memory_total_bytes?: number;
      memory_used_bytes?: number;
      utilization_percent?: number;
      driver?: string;
    } | null;
    disk_free_bytes?: number;
    [key: string]: unknown;
  };
  capabilities?: {
    id: string;
    label: string;
    status: Status;
    reason?: string;
  }[];
  [key: string]: unknown;
}
export interface RunRequest {
  operation: "check" | "route" | "optimize";
  scope?: string[];
  mission?: Record<string, unknown>;
  budget_seconds?: number;
  seed?: number;
}
