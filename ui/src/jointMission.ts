import { buildMission, emptyMission, type MissionForm } from "./mission";
export interface DemandForm {
  key: string;
  id: string;
  alternatives: MissionForm[];
}
export interface JointMissionForm {
  demands: DemandForm[];
  max_joint_candidates: string;
  max_paths_per_alternative: string;
}
export function newDemand(id: string): DemandForm {
  return { key: crypto.randomUUID(), id, alternatives: [{ ...emptyMission }] };
}
export function newJointMission(): JointMissionForm {
  return {
    demands: [newDemand("demand-1")],
    max_joint_candidates: "32",
    max_paths_per_alternative: "4",
  };
}
export function buildJointMission(
  form: JointMissionForm,
): Record<string, unknown> {
  const limit = (value: string, max: number, name: string) => {
    const number = Number(value);
    if (
      !value.trim() ||
      !Number.isInteger(number) ||
      number < 1 ||
      number > max
    )
      throw new Error(`${name} must be an integer between 1 and ${max}.`);
    return number;
  };
  if (form.demands.length < 1 || form.demands.length > 16)
    throw new Error("Supply between 1 and 16 route demands.");
  const ids = new Set<string>();
  const route_demands = form.demands.map((d) => {
    const id = d.id.trim();
    if (!/^[A-Za-z0-9_.:-]{1,120}$/.test(id))
      throw new Error(
        "Demand IDs need 1–120 letters, numbers, dots, colons, underscores or hyphens.",
      );
    if (ids.has(id)) throw new Error(`Demand ID ${id} is repeated.`);
    ids.add(id);
    if (!d.alternatives.length || d.alternatives.length > 16)
      throw new Error(`${id} needs 1–16 explicit alternatives.`);
    return {
      id,
      alternatives: d.alternatives.map((a, i) => {
        try {
          return buildMission(a);
        } catch (e) {
          throw new Error(
            `${id} · alternative ${i + 1}: ${(e as Error).message}`,
          );
        }
      }),
    };
  });
  return {
    route_demands,
    max_joint_candidates: limit(
      form.max_joint_candidates,
      256,
      "Joint candidate limit",
    ),
    max_paths_per_alternative: limit(
      form.max_paths_per_alternative,
      32,
      "Paths per alternative",
    ),
  };
}
