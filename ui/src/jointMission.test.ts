import { describe, it, expect } from "vitest";
import { buildJointMission, type JointMissionForm } from "./jointMission";
import { emptyMission } from "./mission";
const option = {
  ...emptyMission,
  start: "0 0 0",
  end: "2 0 0",
  diameter_m: ".1",
  insulation_m: "0",
  bend_radius_m: ".2",
  minimum_straight_m: ".1",
  clearance_m: ".05",
  zone_min: "-1 -1 -1",
  zone_max: "3 3 3",
};
const mission: JointMissionForm = {
  demands: [
    {
      key: "a",
      id: "supply",
      alternatives: [option, { ...option, start: "0 1 0", end: "2 1 0" }],
    },
    {
      key: "b",
      id: "return",
      alternatives: [{ ...option, start: "0 2 0", end: "2 2 0" }],
    },
  ],
  max_joint_candidates: "32",
  max_paths_per_alternative: "4",
};
describe("explicit simultaneous route requests", () => {
  it("preserves every demand and authorized alternative as a full physical scenario", () => {
    const built = buildJointMission(mission) as {
      route_demands: { id: string; alternatives: Record<string, unknown>[] }[];
    };
    expect(
      built.route_demands.map((d) => [d.id, d.alternatives.length]),
    ).toEqual([
      ["supply", 2],
      ["return", 1],
    ]);
    expect(built.route_demands[0].alternatives[1]).toMatchObject({
      start: [0, 1, 0],
      end: [2, 1, 0],
      diameter_m: 0.1,
      clearance_m: 0.05,
    });
  });
  it("rejects a partial alternative with its exact demand and option location", () =>
    expect(() =>
      buildJointMission({
        ...mission,
        demands: [
          {
            ...mission.demands[0],
            alternatives: [option, { ...option, insulation_m: "" }],
          },
        ],
      }),
    ).toThrow("supply · alternative 2"));
  it("rejects duplicate or empty demand identifiers", () => {
    expect(() =>
      buildJointMission({
        ...mission,
        demands: [mission.demands[0], { ...mission.demands[1], id: "supply" }],
      }),
    ).toThrow("repeated");
    expect(() =>
      buildJointMission({
        ...mission,
        demands: [{ ...mission.demands[0], id: "" }],
      }),
    ).toThrow("Demand IDs");
  });
  it("does not coerce missing or fractional search limits", () => {
    expect(() =>
      buildJointMission({ ...mission, max_joint_candidates: "" }),
    ).toThrow("integer");
    expect(() =>
      buildJointMission({ ...mission, max_paths_per_alternative: "1.5" }),
    ).toThrow("integer");
  });
});
