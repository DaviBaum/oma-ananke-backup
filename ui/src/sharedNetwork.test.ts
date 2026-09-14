import { describe, expect, it } from "vitest";
import { candidateEntityIds } from "./candidateGeometry";
import {
  componentDemandIds,
  componentLines,
  parseSharedNetwork,
  sharedNetworkExample,
} from "./sharedNetwork";
import type { Candidate, NetworkSpec } from "./types";

function example() {
  return sharedNetworkExample([20, -5, 3], 0.1, 0.02, 1, 0.2);
}
function change(mutate: (value: ReturnType<typeof example>) => void) {
  const value = example();
  mutate(value);
  return () => parseSharedNetwork(JSON.stringify(value));
}
function graph(value: ReturnType<typeof example>) {
  return (value.network_alternatives as NetworkSpec[])[0];
}
describe("unique shared-network UI contract", () => {
  it("retains one physical trunk across two demand paths without fabricating flow", () => {
    const value = example(),
      { mission, networks } = parseSharedNetwork(JSON.stringify(value)),
      n = networks[0];
    expect(mission).toEqual(value);
    expect(mission.physics).toBeUndefined();
    expect(n.components).toHaveLength(4);
    expect(componentDemandIds(n, "trunk")).toEqual(["demand-a", "demand-b"]);
    expect(componentDemandIds(n, "arm-b")).toEqual(["demand-b"]);
    expect(componentLines(n.components[1])).toEqual([
      [
        [19.8, -5, 3],
        [20.2, -5, 3],
      ],
      [
        [20, -5, 3],
        [20, -4.8, 3],
      ],
    ]);
  });
  it("rejects duplicated physical components instead of multiplying trunk geometry", () =>
    expect(
      change((v) => graph(v).components.push(graph(v).components[0])),
    ).toThrow("duplicated"));
  it("rejects a proposal-controlled federation datum", () =>
    expect(
      change(
        (v) =>
          (graph(v).source_to_federation_matrix = [
            [1, 0, 0, 500],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
          ]),
      ),
    ).toThrow("pinned source datum"));
  it("preserves the fixed source when editing graph geometry", () =>
    expect(
      change((v) => (graph(v).components[0].geometry.start_m = [19, -5, 3.2])),
    ).toThrow("fixed source"));
  it("rejects an altered sink-to-demand identity", () =>
    expect(
      change((v) => (graph(v).demand_paths[0].demand_id = "unapproved-demand")),
    ).toThrow("membership"));
  it("does not promote a geometric example to service assurance without loads", () =>
    expect(change((v) => (v.target_modality = "ENGINEERING_SERVICE"))).toThrow(
      "Flow",
    ));
  it("rejects omitted insulation rather than interpreting it as zero", () =>
    expect(change((v) => delete v.insulation_m)).toThrow("Insulation"));
  it("produces selectable unique native component IDs, alongside existing routes", () => {
    const n = graph(example());
    const candidate = {
      routes: [{ id: "old-route" }],
      networks: [
        { id: "network-record", component_ids: n.components.map((c) => c.id) },
      ],
    } as Candidate;
    expect([...candidateEntityIds(candidate)]).toEqual([
      "old-route",
      "network-record:trunk",
      "network-record:junction",
      "network-record:arm-a",
      "network-record:arm-b",
    ]);
    expect(candidateEntityIds(null).size).toBe(0);
  });
});
