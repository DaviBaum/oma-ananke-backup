import type { Vec3 } from "./types";
export interface MissionForm {
  system_type: string;
  start: string;
  end: string;
  diameter_m: string;
  insulation_m: string;
  bend_radius_m: string;
  minimum_straight_m: string;
  clearance_m: string;
  zone_min: string;
  zone_max: string;
  source_port_guid: string;
  sink_port_guid: string;
  terminals: "scenario" | "imported";
  advanced: string;
}
export const emptyMission: MissionForm = {
  system_type: "PRESSURE_PIPE",
  start: "",
  end: "",
  diameter_m: "",
  insulation_m: "",
  bend_radius_m: "",
  minimum_straight_m: "",
  clearance_m: "",
  zone_min: "",
  zone_max: "",
  source_port_guid: "",
  sink_port_guid: "",
  terminals: "scenario",
  advanced: "",
};
export function vector(value: string): Vec3 {
  const numbers = value
    .split(/[,\s]+/)
    .filter(Boolean)
    .map(Number);
  if (numbers.length !== 3 || numbers.some((n) => !Number.isFinite(n)))
    throw new Error(
      "Coordinates require three finite numbers: X, Y, Z in world meters.",
    );
  return numbers as Vec3;
}
export function buildMission(form: MissionForm) {
  const numeric = (key: keyof MissionForm, positive = false) => {
    const value = Number(form[key]);
    if (
      !form[key].trim() ||
      !Number.isFinite(value) ||
      (positive ? value <= 0 : value < 0)
    )
      throw new Error(
        `Supply ${positive ? "a positive" : "an explicit nonnegative"} ${key.replaceAll("_", " ")}.`,
      );
    return value;
  };
  const start = vector(form.start),
    end = vector(form.end),
    diameter_m = numeric("diameter_m", true),
    insulation_m = numeric("insulation_m"),
    bend_radius_m = numeric("bend_radius_m", true),
    minimum_straight_m = numeric("minimum_straight_m"),
    clearance_m = numeric("clearance_m"),
    min = vector(form.zone_min),
    max = vector(form.zone_max);
  if (start.every((n, i) => n === end[i]))
    throw new Error("The source and sink positions must be distinct.");
  if (min.some((n, i) => n >= max[i]))
    throw new Error("Every allowed-zone minimum must be below its maximum.");
  if ([start, end].some((p) => p.some((n, i) => n < min[i] || n > max[i])))
    throw new Error(
      "Source and sink positions must lie inside the permitted routing zone.",
    );
  if (bend_radius_m <= diameter_m / 2 + insulation_m)
    throw new Error("The bend radius must exceed the insulated outer radius.");
  if (
    form.terminals === "imported" &&
    (!form.source_port_guid.trim() || !form.sink_port_guid.trim())
  )
    throw new Error(
      "Both explicit IFC port GUIDs are required for imported terminal connections.",
    );
  let advanced: Record<string, unknown> = {};
  if (form.advanced.trim()) {
    advanced = JSON.parse(form.advanced);
    if (!advanced || typeof advanced !== "object" || Array.isArray(advanced))
      throw new Error("Additional mission inputs must be a JSON object.");
  }
  const base: Record<string, unknown> = {
    start,
    end,
    system_type: form.system_type,
    diameter_m,
    insulation_m,
    bend_radius_m,
    minimum_straight_m,
    clearance_m,
    allowed_zone: { min, max },
    scenario_terminals: form.terminals === "scenario",
    provenance: "user_supplied_scenario",
    assumptions: [
      "Routing coordinates, sections, fittings and allowed zone were explicitly entered in the local workbench; they are scenario assumptions, not imported facts.",
    ],
  };
  if (form.terminals === "imported") {
    base.source_port_guid = form.source_port_guid.trim();
    base.sink_port_guid = form.sink_port_guid.trim();
  }
  for (const key of Object.keys(advanced))
    if (key in base)
      throw new Error(
        `Additional JSON cannot override the explicit ${key} field.`,
      );
  return { ...base, ...advanced };
}
