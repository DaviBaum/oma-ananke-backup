import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { api } from "./api";
import { candidateEntityIds } from "./candidateGeometry";
import {
  attachOpening,
  emptyOpening,
  openingIsCurrent,
  openingRequest,
  type OpeningForm,
} from "./opening";
import OpeningFields from "./OpeningFields";
import OpeningEvidence from "./OpeningEvidence";
import type {
  Candidate,
  OpeningEdit,
  OpeningHostInspection,
  Snapshot,
} from "./types";

const hash = "a".repeat(64);
const probe: OpeningHostInspection = {
  status: "ELIGIBLE",
  project_id: "p",
  state_root: "root",
  entity_id: `${hash}:142`,
  source_id: hash,
  source_sha256: hash,
  reason: "Native rectangular host agrees",
  opening_permission: "NOT_INFERRED",
  requires_explicit_permission: true,
  engineering_scope: "SCENARIO_GEOMETRY_ONLY",
  host: {
    host_guid: "ifc-guid",
    host_step_id: 142,
    host_geometry_root: "b".repeat(64),
    source_sha256: hash,
    host_bounds_local_m: [
      ["-2", "-1/5", "0"],
      ["2", "1/5", "3"],
    ],
    host_local_to_source_matrix_m: [
      [1, 0, 0, 0],
      [0, 1, 0, 0],
      [0, 0, 1, 0],
      [0, 0, 0, 1],
    ],
  },
};
const form: OpeningForm = {
  cutMin: "-.5 -.4 1",
  cutMax: ".5 .4 2",
  allowedMin: "-.6 -.5 .9",
  allowedMax: ".6 .5 2.1",
  axis: "1",
  statement: "Explicitly authorized fixture opening.",
  evidence: "",
  confirmed: true,
};

describe("explicit native host opening", () => {
  it("has no default permission, cut or through-axis", () => {
    expect(emptyOpening.confirmed).toBe(false);
    expect(emptyOpening.statement).toBe("");
    expect(emptyOpening.axis).toBe("");
    expect(() => openingRequest(probe, emptyOpening)).toThrow(
      "Explicitly confirm",
    );
  });
  it("pins real identity and permission while attaching the actual chosen cut", () => {
    const mission = attachOpening({ clearance_m: 0.1 }, probe, form);
    expect(mission.source_id).toBe(hash);
    expect(mission.authorized_opening).toMatchObject({
      source_sha256: hash,
      host_guid: "ifc-guid",
      host_step_id: 142,
      host_geometry_root: "b".repeat(64),
      through_axis: 1,
      opening_bounds_local_m: { min: [-0.5, -0.4, 1], max: [0.5, 0.4, 2] },
      permission: {
        evidence_roots: [],
        engineering_scope: "SCENARIO_GEOMETRY_ONLY",
      },
    });
  });
  it("rejects missing permission, malformed axes, nonfinite/inverted/escaping bounds and fake evidence", () => {
    for (const patch of [
      { confirmed: false },
      { statement: "" },
      { axis: "" },
      { axis: "3" },
      { cutMin: "NaN 0 0" },
      { cutMax: "-1 0 0" },
      { cutMax: "1 .4 2" },
      { evidence: "not-a-root" },
    ])
      expect(() => openingRequest(probe, { ...form, ...patch })).toThrow();
  });
  it("rejects source or host mismatches and additional JSON override", () => {
    expect(() => openingRequest({ ...probe, status: "UNKNOWN" }, form)).toThrow(
      "eligible",
    );
    expect(() =>
      openingRequest({ ...probe, entity_id: `${hash}:143` }, form),
    ).toThrow("eligible");
    expect(() =>
      attachOpening({ source_id: "different" }, probe, form),
    ).toThrow("source must match");
    expect(() =>
      attachOpening({ authorized_opening: {} }, probe, form),
    ).toThrow("duplicate");
  });
  it("invalidates on project, root or history selection changes", () => {
    const snapshot = { project: { id: "p", state_root: "root" } } as Snapshot;
    expect(openingIsCurrent(probe, snapshot, false)).toBe(true);
    expect(openingIsCurrent(probe, snapshot, true)).toBe(false);
    expect(
      openingIsCurrent(
        probe,
        { ...snapshot, project: { ...snapshot.project, id: "other" } },
        false,
      ),
    ).toBe(false);
    expect(
      openingIsCurrent(
        probe,
        { ...snapshot, project: { ...snapshot.project, state_root: "next" } },
        false,
      ),
    ).toBe(false);
    expect(openingIsCurrent(probe, null, false)).toBe(false);
  });
  it("keeps edited host out of baseline compare geometry and exposes scope without granting clearance", () => {
    const edit = {
      host_entity_id: probe.entity_id,
      effective_source_file: "final.ifc",
    } as OpeningEdit;
    const ids = candidateEntityIds({
      routes: [{ id: "route" }],
      opening_edit: edit,
    } as Candidate);
    expect([...ids]).toEqual([probe.entity_id, "route"]);
    const markup = renderToStaticMarkup(
      <OpeningEvidence edit={edit} onInspect={() => {}} />,
    );
    expect(markup).toContain("final.ifc");
    expect(markup).toContain("Structural, fire and access adequacy");
    expect(markup).toContain("History");
    expect(markup).not.toContain("PASS");
  });
  it("disables a stale form and retains the exact rational host descriptor for inspection", () => {
    const markup = renderToStaticMarkup(
      <OpeningFields
        probe={probe}
        value={emptyOpening}
        onChange={() => {}}
        stale
      />,
    );
    expect(markup).toContain('fieldset disabled=""');
    expect(markup).toContain("-1/5");
    expect(markup).toContain("local frame");
    expect(markup).not.toContain('checked=""');
  });
  it("pins revision zero and encodes source identity on the native inspection request", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(probe)));
    vi.stubGlobal("fetch", fetcher);
    try {
      const abort = new AbortController();
      await api.openingHost("p", "source:142", 0, abort.signal);
      expect(fetcher.mock.calls[0][0]).toBe(
        "/api/projects/p/opening-host?entity_id=source%3A142&revision=0",
      );
      expect(fetcher.mock.calls[0][1].signal).toBe(abort.signal);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
