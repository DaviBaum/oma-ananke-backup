import { vector } from "./mission";
import type { OpeningHostInspection, OpeningRequest, Snapshot } from "./types";

export interface OpeningForm {
  cutMin: string;
  cutMax: string;
  allowedMin: string;
  allowedMax: string;
  axis: string;
  statement: string;
  evidence: string;
  confirmed: boolean;
}
export const emptyOpening: OpeningForm = {
  cutMin: "",
  cutMax: "",
  allowedMin: "",
  allowedMax: "",
  axis: "",
  statement: "",
  evidence: "",
  confirmed: false,
};
export function openingIsCurrent(
  probe: OpeningHostInspection,
  snapshot: Snapshot | null,
  viewingOtherState: boolean,
) {
  return (
    !viewingOtherState &&
    !!snapshot &&
    probe.project_id === snapshot.project.id &&
    probe.state_root === snapshot.project.state_root
  );
}
export function openingRequest(
  probe: OpeningHostInspection,
  form: OpeningForm,
): OpeningRequest {
  const host = probe.host;
  if (
    probe.status !== "ELIGIBLE" ||
    !host ||
    host.source_sha256 !== probe.source_sha256 ||
    probe.entity_id !== `${probe.source_id}:${host.host_step_id}`
  )
    throw new Error(
      "The native inspection does not bind an eligible imported host.",
    );
  if (
    !form.confirmed ||
    form.statement.trim().length < 10 ||
    form.statement.length > 4000
  )
    throw new Error(
      "Explicitly confirm geometric edit permission and supply its statement (10–4,000 characters).",
    );
  if (!["0", "1", "2"].includes(form.axis))
    throw new Error(
      "Choose the through-axis in the inspected host's local frame.",
    );
  const cut = { min: vector(form.cutMin), max: vector(form.cutMax) },
    allowed = { min: vector(form.allowedMin), max: vector(form.allowedMax) };
  if (
    cut.min.some((v, i) => v >= cut.max[i]) ||
    allowed.min.some((v, i) => v >= allowed.max[i])
  )
    throw new Error(
      "Opening and permitted volumes require three positive dimensions.",
    );
  if (cut.min.some((v, i) => v < allowed.min[i] || cut.max[i] > allowed.max[i]))
    throw new Error(
      "The complete opening must remain inside the explicitly permitted volume.",
    );
  const evidence = form.evidence.split(/[,\s]+/).filter(Boolean);
  if (evidence.some((root) => !/^[a-f0-9]{64}$/.test(root)))
    throw new Error(
      "Evidence roots must be lowercase SHA-256 hashes; leave empty when none is supplied.",
    );
  return {
    source_sha256: probe.source_sha256,
    host_guid: host.host_guid,
    host_step_id: host.host_step_id,
    host_geometry_root: host.host_geometry_root,
    opening_bounds_local_m: cut,
    allowed_opening_bounds_local_m: allowed,
    through_axis: Number(form.axis) as 0 | 1 | 2,
    permission: {
      mode: "EXPLICIT_USER_GEOMETRIC_EDIT",
      statement: form.statement.trim(),
      evidence_roots: [...new Set(evidence)],
      engineering_scope: "SCENARIO_GEOMETRY_ONLY",
    },
  };
}

export function attachOpening(
  mission: Record<string, unknown>,
  probe: OpeningHostInspection,
  form: OpeningForm,
) {
  if ("authorized_opening" in mission)
    throw new Error(
      "The inspected opening form supplies authorized_opening; remove its duplicate from additional JSON.",
    );
  if (mission.source_id !== undefined && mission.source_id !== probe.source_id)
    throw new Error("The route source must match the inspected opening host.");
  return {
    ...mission,
    source_id: probe.source_id,
    authorized_opening: openingRequest(probe, form),
  };
}
