import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import SharedNetworkFields from "./SharedNetworkFields";
import NetworkLineage from "./NetworkLineage";
import {
  buildNetworkRevision,
  networkChangedIds,
  networkRevisionIsCurrent,
  prepareNetworkRevision,
} from "./networkRevision";
import { sharedNetworkExample } from "./sharedNetwork";
import type { NetworkSpec, PhysicalNetwork, Snapshot } from "./types";

function accepted(): Snapshot {
  const scenario = sharedNetworkExample([20, -5, 3], 0.1, 0.02, 1, 0.2);
  const spec = (scenario.network_alternatives as NetworkSpec[])[0];
  const network = {
    id: spec.network_id,
    network_spec: spec,
    component_ids: spec.components.map((c) => c.id),
    network_contract: {
      scenario,
      selected_alternative: spec.network_id,
      source_id: "immutable-source",
    },
  } as PhysicalNetwork;
  return {
    project: {
      id: "project-a",
      name: "Accepted",
      revision: 2,
      state_root: "accepted-root",
      status: "ACCEPTED",
    },
    networks: [network],
    history: [],
    entities: [],
  } as unknown as Snapshot;
}

describe("explicit accepted network revisions", () => {
  it("preserves every fixed field and normalizes the pinned source while changing only the physical menu", () => {
    const snapshot = accepted(),
      scenario = snapshot.networks![0].network_contract!.scenario;
    scenario.physics = { supplied_boundary_assumption: "unchanged" };
    scenario.future_authority_field = { protected: true };
    const seed = prepareNetworkRevision(snapshot);
    const alternatives = structuredClone(seed.alternatives) as NetworkSpec[];
    alternatives[0].network_id = "replacement";
    const mission = buildNetworkRevision(
      seed,
      JSON.stringify(alternatives),
    ).mission;
    expect(mission.source_id).toBe("immutable-source");
    expect(mission.replace_network_id).toBe("editable-example");
    expect(mission.physics).toEqual(scenario.physics);
    expect(mission.future_authority_field).toEqual(
      scenario.future_authority_field,
    );
    expect(mission.network_alternatives).toEqual(alternatives);
    expect((scenario.network_alternatives as NetworkSpec[])[0].network_id).toBe(
      "editable-example",
    );
  });
  it("rejects full-mission injection and moved service terminals", () => {
    const seed = prepareNetworkRevision(accepted());
    expect(() =>
      buildNetworkRevision(
        seed,
        JSON.stringify({ ...seed.fixed, start_m: [0, 0, 0] }),
      ),
    ).toThrow("array only");
    const alternatives = structuredClone(seed.alternatives) as NetworkSpec[];
    alternatives[0].components[0].geometry.start_m = [0, 0, 0];
    expect(() =>
      buildNetworkRevision(seed, JSON.stringify(alternatives)),
    ).toThrow("fixed source");
  });
  it("gates unaccepted, historical, mismatched-contract and mixed network states", () => {
    const snapshot = accepted();
    snapshot.project.status = "CHECKED";
    expect(() => prepareNetworkRevision(snapshot)).toThrow("Publish");
    snapshot.project.status = "ACCEPTED";
    snapshot.project.current_state_root = "new-head";
    expect(() => prepareNetworkRevision(snapshot)).toThrow(
      "current accepted head",
    );
    delete snapshot.project.current_state_root;
    snapshot.entities.push({ id: "route", ifc_type: "PhysicalRoute" });
    expect(() => prepareNetworkRevision(snapshot)).toThrow("no separate route");
    snapshot.entities = [];
    snapshot.networks![0].network_contract!.selected_alternative = "other";
    expect(() => prepareNetworkRevision(snapshot)).toThrow(
      "immutable scenario",
    );
  });
  it("recognizes the exact accepted revision from durable history after a later check status", () => {
    const snapshot = accepted();
    snapshot.project.status = "CHECKED";
    snapshot.history = [
      { revision: 2, state_root: "accepted-root", status: "ACCEPTED" },
    ];
    expect(prepareNetworkRevision(snapshot).baseRevision).toBe(2);
    snapshot.history[0].state_root = "different";
    expect(() => prepareNetworkRevision(snapshot)).toThrow("Publish");
  });
  it("invalidates an open editor on any project, head, revision or historical-view change", () => {
    const snapshot = accepted(),
      seed = prepareNetworkRevision(snapshot);
    expect(networkRevisionIsCurrent(seed, snapshot, false)).toBe(true);
    expect(networkRevisionIsCurrent(seed, snapshot, true)).toBe(false);
    expect(networkRevisionIsCurrent(seed, null, false)).toBe(false);
    for (const patch of [
      { id: "other" },
      { state_root: "changed" },
      { revision: 3 },
    ])
      expect(
        networkRevisionIsCurrent(
          seed,
          { ...snapshot, project: { ...snapshot.project, ...patch } },
          false,
        ),
      ).toBe(false);
  });
  it("renders fixed requirements read-only and leaves only the alternative array editable", () => {
    const seed = prepareNetworkRevision(accepted());
    const markup = renderToStaticMarkup(
      <SharedNetworkFields
        revision={seed}
        value={JSON.stringify(seed.alternatives)}
        onChange={() => {}}
      />,
    );
    expect(markup).toMatch(
      /aria-label="Fixed network requirements"[^>]*readOnly=""/,
    );
    expect(markup).toContain('aria-label="Replacement alternatives JSON"');
    expect(markup).not.toContain("Create an editable two-sink example");
    expect(markup).toContain("fresh native checks");
  });
  it("reports the deduplicated old/new union and distinguishes previous graph from selected native state", () => {
    const network = accepted().networks![0];
    network.network_contract!.revision = {
      base_root: "base",
      replaced_network_id: "old-tree",
      previous_component_ids: ["old-tree:trunk", "editable-example:arm-a"],
      previous_network_root: "old-network",
      previous_contract_root: "old-contract",
      fixed_requirements_root: "fixed",
    };
    expect(networkChangedIds(network).size).toBe(5);
    const markup = renderToStaticMarkup(
      <NetworkLineage network={network} onInspect={() => {}} />,
    );
    expect(markup).toContain("5 unique changed IDs");
    expect(markup).toContain("Previous parts");
    expect(markup).toContain("Proposed parts");
    expect(markup).toContain("viewport shows this selected state");
  });
});
