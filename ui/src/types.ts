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
  networks?: PhysicalNetwork[];
  validation_advisories?: ValidationAdvisory[];
  id: string;
  run_id?: string;
  state_root: string;
  status: Status;
  objective: Record<string, number>;
  check?: {
    status: Status;
    reason?: string;
    scope?: unknown;
    applicability?: "CURRENT" | "STALE_EXECUTABLE" | "WRONG_ROOT" | string;
    checker_version?: string;
    current_checker_version?: string;
  };
  changed_ids: string[];
  created_at?: string;
  routes: Route[];
  [key: string]: unknown;
}
export type NetworkService = "PRESSURE_PIPE" | "ROUND_DUCT" | "FIRE_PROTECTION";
export type NetworkSlot = "a" | "b" | "branch";
export type Matrix4 = [number[], number[], number[], number[]];
export interface NetworkComponent {
  id: string;
  kind: "segment" | "elbow" | "tee";
  system_type: NetworkService;
  diameter_m: number;
  insulation_m: number;
  ports: Partial<Record<NetworkSlot, "SINK" | "SOURCE">>;
  geometry: {
    start_m?: Vec3;
    end_m?: Vec3;
    center_m?: Vec3;
    normal?: Vec3;
    angle_rad?: number;
    bend_radius_m?: number;
    frame_m?: Matrix4;
    trunk_takeout_m?: number;
    branch_takeout_m?: number;
  };
}
export interface NetworkSpec {
  schema: "oma-physical-network/1";
  network_id: string;
  system_type: NetworkService;
  source_to_federation_matrix?: Matrix4;
  components: NetworkComponent[];
  connections: {
    source: { component: string; port: NetworkSlot };
    sink: { component: string; port: NetworkSlot };
  }[];
  source: { component: string; port: NetworkSlot };
  sinks: { id: string; endpoint: { component: string; port: NetworkSlot } }[];
  demand_paths: {
    demand_id: string;
    sink_id: string;
    steps: {
      component: string;
      entry_port: NetworkSlot;
      exit_port: NetworkSlot;
    }[];
  }[];
}
export interface PhysicalNetwork {
  id: string;
  demand_ids: string[];
  component_ids: string[];
  port_ids: string[];
  service: string;
  section: Record<string, unknown>;
  geometry_artifact: string;
  status: string;
  network_spec: NetworkSpec;
  added_parts: {
    component_id: string;
    ifc_guid: string;
    ports: Record<string, string>;
    kind: string;
  }[];
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
export interface AssuranceRecord {
  validation_advisories?: ValidationAdvisory[];
  candidate_id: string;
  candidate_root: string;
  support_status: string;
  reason?: string;
  recorded_engineering_status?: string;
  scope?: string;
  assessment_context?: Record<string, unknown>;
  recorded_context?: Record<string, unknown>;
  independent_assurance_check?: { status: string; reason?: string };
  assumption_ledger?: {
    id: string;
    kind: string;
    statement: string;
    status: string;
    technical_truth?: string;
  }[];
  dispositions?: {
    id: string;
    status: string;
    reason: string;
    scope: string;
    truth_basis?: string;
    [key: string]: unknown;
  }[];
  certificate?: {
    complete?: boolean;
    cores?: string[][];
    excluded_foundations?: Record<string, string>;
    [key: string]: unknown;
  };
  theory?: {
    foundations?: { id: string; description: string; [key: string]: unknown }[];
    [key: string]: unknown;
  };
  external_evidence_cuts?: {
    status?: string;
    cuts?: string[][];
    [key: string]: unknown;
  };
  fresh_physical_recheck?: string;
  current_external_file_bytes?: string;
  whole_building_certification?: string;
  global_optimality?: string;
  [key: string]: unknown;
}
export interface ValidationAdvisory {
  id: string;
  status: string;
  route_ids: string[];
  claim: string;
  reason: string;
  source: string;
  scope: string;
  resolution_contract: string;
}
export interface DependencyRecord {
  before_root: string;
  after_root: string;
  changed_authoritative_inputs: string[];
  conservatively_affected: string[];
  semantic_output_changes: string[];
  recomputed: string[];
  reused: string[];
  cold_equivalent: boolean;
  input_roots: Record<string, string>;
  dependencies: Record<string, string[]>;
  artifacts: Record<string, unknown>;
  scope: string;
  elapsed_seconds?: number;
  physical_checks_reused_across_roots?: boolean;
  [key: string]: unknown;
}
