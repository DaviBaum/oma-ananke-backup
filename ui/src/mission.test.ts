import { describe, it, expect } from "vitest";
import { buildMission, emptyMission, vector } from "./mission";
const valid = {
  ...emptyMission,
  start: "0, 0, 0",
  end: "2 3 4",
  diameter_m: "0.1",
  insulation_m: "0.02",
  bend_radius_m: "0.2",
  minimum_straight_m: "0.1",
  clearance_m: "0",
  zone_min: "-1,-1,-1",
  zone_max: "5,5,5",
};
describe("explicit engineering scenario form", () => {
  it("preserves physical section and explicit zero clearance independently", () =>
    expect(buildMission(valid)).toMatchObject({
      diameter_m: 0.1,
      insulation_m: 0.02,
      clearance_m: 0,
      scenario_terminals: true,
      allowed_zone: { min: [-1, -1, -1], max: [5, 5, 5] },
    }));
  it("refuses to substitute zero for omitted insulation", () =>
    expect(() => buildMission({ ...valid, insulation_m: "" })).toThrow(
      "explicit nonnegative",
    ));
  it("rejects nonfinite coordinates", () =>
    expect(() => vector("0 NaN 2")).toThrow("finite"));
  it("rejects a fitting radius inside its insulated body", () =>
    expect(() => buildMission({ ...valid, bend_radius_m: ".06" })).toThrow(
      "insulated",
    ));
  it("requires a real allowed volume containing both terminals", () =>
    expect(() => buildMission({ ...valid, zone_max: "1 1 1" })).toThrow(
      "inside",
    ));
  it("requires imported port identities", () =>
    expect(() => buildMission({ ...valid, terminals: "imported" })).toThrow(
      "GUIDs",
    ));
  it("prevents hidden advanced JSON from overriding declared UI constraints", () =>
    expect(() =>
      buildMission({ ...valid, advanced: '{"clearance_m":-1}' }),
    ).toThrow("cannot override"));
});
